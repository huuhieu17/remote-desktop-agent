# core/config.py
import json, os, uuid

CONFIG_PATH = "config.json"

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.load()
        return cls._instance

    def load(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
        else:
            data = {}

        self.device_id = data.get("device_id") or str(uuid.uuid4())
        self.telegram_token = data.get("telegram_token", "")
        self.telegram_chat_id = data.get("telegram_chat_id", "")
        self.save()

    def save(self):
        with open(CONFIG_PATH, "w") as f:
            json.dump({
                "device_id": self.device_id,
                "telegram_token": self.telegram_token,
                "telegram_chat_id": self.telegram_chat_id,
            }, f, indent=2)

    def revoke_device_id(self):
        self.device_id = str(uuid.uuid4())
        self.save()
