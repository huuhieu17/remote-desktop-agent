# core/telegram_service.py
import requests
from core.config import Config

class TelegramService:
    def __init__(self):
        self.cfg = Config()

    def send_message(self, text: str):
        if not self.cfg.telegram_token or not self.cfg.telegram_chat_id:
            print("⚠️ Telegram chưa được cấu hình")
            return
        url = f"https://api.telegram.org/bot{self.cfg.telegram_token}/sendMessage"
        payload = {"chat_id": self.cfg.telegram_chat_id, "text": text}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"❌ Telegram error: {e}")

    def send_telegram_photo(self, photo_path):
        url = f"https://api.telegram.org/bot{self.cfg.telegram_token}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, data={"chat_id": self.cfg.telegram_chat_id}, files={"photo": photo})
