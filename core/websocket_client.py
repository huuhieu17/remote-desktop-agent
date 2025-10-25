# core/websocket_client.py
import asyncio
import websockets
import json
from core.config import Config
from core.telegram_service import TelegramService
from core.command_handler import CommandHandler

SERVER_URL = "ws://localhost:8000/ws/agent"

class WebSocketClient:
    def __init__(self, on_chat_callback=None, on_status_callback=None):
        self.cfg = Config()
        self.telegram = TelegramService()
        self.handler = CommandHandler()
        self.on_chat_callback = on_chat_callback
        self.on_status_callback = on_status_callback
        self.ws = None

    async def connect(self):
        uri = f"{SERVER_URL}?device_id={self.cfg.device_id}"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    self.ws = ws
                    print("✅ Connected to server")
                    self.telegram.send_message("🟢Agent đã kết nối server")
                    if self.on_status_callback:
                        self.on_status_callback(True)
                    await self.listen(ws)
            except Exception as e:
                print(f"⚠️ WS disconnected: {e}, retrying...")
                if self.on_status_callback:
                    self.on_status_callback(False)
                await asyncio.sleep(5)

    async def listen(self, ws):
        async for message in ws:
            try:
                data = json.loads(message)
                if data.get("type") == "command":
                    self.handler.enqueue_command(data)
                elif data.get("type") == "chat":
                    msg = f"{data.get('from')}: {data.get('message')}"
                    print(f"💬 Chat: {msg}")
                    if self.on_chat_callback:
                        self.on_chat_callback(msg)
                    self.telegram.send_message(f"💬 {msg}")
            except Exception as e:
                print(f"Error handling WS message: {e}")

    async def send_chat(self, text: str):
        if not self.ws:
            print("⚠️ No active connection")
            return
        try:
            payload = json.dumps({"type": "chat", "message": text})
            await self.ws.send(payload)
        except Exception as e:
            print(f"⚠️ Send chat failed: {e}")

    
    async def send_result(self, request_id: str, result: dict):
        packet = {
            "type": "command_result",
            "request_id": request_id,
            "result": result
        }
        await self.ws.send(json.dumps(packet))
