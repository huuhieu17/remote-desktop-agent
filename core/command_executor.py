import os
import psutil
import pyautogui
from datetime import datetime
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Optional
from core.telegram_service import TelegramService


class ICommand(ABC):
    @abstractmethod
    def execute(self) -> dict:
        """Thực thi lệnh và trả kết quả (nếu có)"""
        pass


# ===== Concrete Commands =====
class ShutdownCommand(ICommand):
    def execute(self):
        os.system("shutdown /s /t 0")
        return {"status": "success", "message": "Shutting down..."}


class RestartCommand(ICommand):
    def execute(self):
        os.system("shutdown /r /t 0")
        return {"status": "success", "message": "Restarting..."}


class LockCommand(ICommand):
    def execute(self):
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return {"status": "success", "message": "Locked workstation"}


class KillAppCommand(ICommand):
    def __init__(self, target: str):
        self.target = target

    def execute(self):
        if not self.target:
            return {"status": "error", "message": "Missing target app name"}
        count = 0
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and self.target.lower() in proc.info['name'].lower():
                proc.kill()
                count += 1
        msg = f"Killed {count} process(es) matching '{self.target}'"
        print(f"💀 {msg}")
        return {"status": "success", "message": msg}


class WifiCommand(ICommand):
    def __init__(self, enable: bool):
        self.enable = enable

    def execute(self):
        state = "enabled" if self.enable else "disabled"
        os.system(f'netsh interface set interface "Wi-Fi" admin={state}')
        return {"status": "success", "message": f"Wi-Fi {state}"}


class BluetoothCommand(ICommand):
    def __init__(self, enable: bool):
        self.enable = enable

    def execute(self):
        try:
            state = "on" if self.enable else "off"
            subprocess.run(
                ["powershell", f"Set-Service bthserv -StartupType {'automatic' if self.enable else 'disabled'}"],
                shell=True
            )
            subprocess.run(
                ["powershell", f"Start-Service bthserv" if self.enable else "Stop-Service bthserv"],
                shell=True
            )
            msg = f"Bluetooth turned {state}"
            print(f"🟦 {msg}")
            return {"status": "success", "message": msg}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MessageCommand(ICommand):
    def __init__(self, text: str):
        self.text = text

    def execute(self):
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, self.text, "Message from Admin", 1)
        return {"status": "success", "message": f"Message shown: {self.text}"}


class ScreenCaptureCommand(ICommand):
    def __init__(self):
        self.telegram = TelegramService()
    def execute(self):
        image = pyautogui.screenshot()
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_path = os.path.join(os.getcwd(), "screenshots")
        os.makedirs(save_path, exist_ok=True)
        full_path = os.path.join(save_path, filename)
        image.save(full_path)
        print(f"[Screenshot saved] {full_path}")
        self.telegram.send_telegram_photo(full_path)
        return {"status": "success", "file": full_path}


class ShellCommand(ICommand):
    def __init__(self, command: str):
        self.command = command
        self.telegram = TelegramService()

    def execute(self):
        if not self.command:
            return {"status": "error", "message": "Empty shell command"}

        print(f"💻 Running shell command: {self.command}")
        try:
            result = subprocess.run(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8"
            )

            output = result.stdout.strip()
            error = result.stderr.strip()

            self.telegram.send_message(
                f"💻 Command: `{self.command}`\n✅ Output:\n{output[:3000]}\n⚠️ Error:\n{error[:3000]}"
            )

            return {
                "status": "success" if result.returncode == 0 else "error",
                "output": output,
                "error": error
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}


# ===== Factory / Executor =====
class CommandExecutor:
    ws_client = None  # sẽ được gán từ agent/main.py

    @staticmethod
    def create(cmd: Dict) -> Optional[ICommand]:
        print(f"cmd: {cmd}")
        action = cmd.get("type")
        if action == "shutdown":
            return ShutdownCommand()
        elif action == "restart":
            return RestartCommand()
        elif action == "kill_app":
            return KillAppCommand(cmd.get("target"))
        elif action == "disable_wifi":
            return WifiCommand(enable=False)
        elif action == "enable_wifi":
            return WifiCommand(enable=True)
        elif action == "disable_bluetooth":
            return BluetoothCommand(enable=False)
        elif action == "enable_bluetooth":
            return BluetoothCommand(enable=True)
        elif action == "lock":
            return LockCommand()
        elif action == "message":
            return MessageCommand(cmd.get("text", ""))
        elif action == "screenshot":
            return ScreenCaptureCommand()
        elif action == "shell":
            return ShellCommand(cmd.get("command", ""))
        else:
            print(f"[⚠️ Unknown Command Type] {action}")
            return None

    @staticmethod
    async def execute(cmd: Dict):
        command = CommandExecutor.create(cmd)
        if not command:
            return

        print(f"⚙️ Executing command: {cmd}")
        try:
            result = command.execute()
        except Exception as e:
            result = {"status": "error", "message": str(e)}

        # gửi kết quả về server nếu có websocket
        if CommandExecutor.ws_client:
            await CommandExecutor.ws_client.send_result(cmd.get("request_id"), result)

        return result
