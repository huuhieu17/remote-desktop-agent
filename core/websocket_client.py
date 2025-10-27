# core/websocket_client.py
import asyncio
import json
import time
import threading
from websocket import WebSocketApp
from core.config import Config
from core.telegram_service import TelegramService
from core.command_handler import CommandHandler

SERVER_URL = "ws://control.imsteve.dev/ws"


class WebSocketClient:
    def __init__(self, on_chat_callback=None, on_status_callback=None):
        self.cfg = Config()
        self.telegram = TelegramService()
        self.handler = CommandHandler()
        self.on_chat_callback = on_chat_callback
        self.on_status_callback = on_status_callback
        self.ws = None
        self._should_reconnect = True

    def _on_open(self, ws):
        print("✅ Connected to server")
        self.telegram.send_message("🟢 Agent đã kết nối server")
        self.telegram.send_message(f"{self.cfg.device_id}")
        if self.on_status_callback:
            self.on_status_callback(True)

    def _on_message(self, ws, message):
        try:
            if not message or not message.strip():
                print("⚠️ Received empty WS message — skipping")
                return
            data = json.loads(message)
            print(f"Received: {data}")
            msg_type = data.get("event")

            if msg_type == "command":
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.handler.enqueue_command(data))
                loop.close()

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
        if self._should_reconnect:
            self._reconnect()

    def _on_error(self, ws, error):
        print(f"⚠️ WS error: {error}")
        if self.on_status_callback:
            self.on_status_callback(False)
        if self._should_reconnect:
            self._reconnect()

    def _reconnect(self):
        """Tự động reconnect khi mất kết nối"""
        print("🔁 Reconnecting in 5s...")
        time.sleep(5)
        self.connect()

    def connect(self):
        """Khởi tạo và chạy WebSocket connection"""
        uri = f"{SERVER_URL}/{self.cfg.device_id}"
        self.ws = WebSocketApp(
            uri,
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error,
        )

        # Dùng thread để không block main thread
        thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        thread.start()

    def send_chat(self, text: str):
        """Gửi tin nhắn chat"""
        if not self.ws:
            print("⚠️ No active connection")
            return
        try:
            payload = json.dumps({"type": "chat", "message": text})
            self.ws.send(payload)
        except Exception as e:
            print(f"⚠️ Send chat failed: {e}")

    def send_result(self, request_id: str, result: dict):
        """Gửi kết quả command"""
        if not self.ws:
            print("⚠️ No active connection")
            return
        try:
            packet = {
                "type": "command_result",
                "request_id": request_id,
                "result": result,
            }
            self.ws.send(json.dumps(packet))
        except Exception as e:
            print(f"⚠️ Send result failed: {e}")

    def stop(self):
        """Ngắt kết nối thủ công"""
        self._should_reconnect = False
        if self.ws:
            self.ws.close()
