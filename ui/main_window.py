# ui/main_window.py
import os
import sys
import tkinter as tk
import asyncio
import threading
import ctypes
from tkinter import messagebox
if sys.platform == "win32":
    import winreg
else:
    winreg = None
from PIL import Image, ImageDraw
import pystray
from core.config import Config
from core.websocket_client import WebSocketClient

def remove_from_startup():
    """Gỡ app khỏi tự khởi động Windows"""
    try:
        key = winreg.HKEY_CURRENT_USER
        key_value = r"Software\Microsoft\Windows\CurrentVersion\Run"
        open_key = winreg.OpenKey(key, key_value, 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteValue(open_key, "WindowManagerAgent")
        winreg.CloseKey(open_key)
        print("🧹 Removed from startup")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️ Failed to remove from startup: {e}")

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.title("Windows Agent")
        self.geometry("600x800")

        # ===== Device Info =====
        tk.Label(self, text="Device ID:").pack()
        self.device_label = tk.Label(self, text=self.cfg.device_id, wraplength=380)
        self.device_label.pack(pady=4)

        button_frame = tk.Frame(self)
        button_frame.pack(pady=5)
        tk.Button(button_frame, text="📋 Copy ID", command=self.copy_device_id).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="📂 Open Config Folder", command=self.open_config_folder).pack(side=tk.LEFT, padx=5)

        tk.Button(self, text="Revoke Device ID", command=self.revoke).pack(pady=5)

        # ===== Telegram Config =====
        tk.Label(self, text="Telegram Token:").pack()
        self.token_entry = tk.Entry(self, width=45)
        self.token_entry.insert(0, self.cfg.telegram_token)
        self.token_entry.pack()

        tk.Label(self, text="Chat ID:").pack()
        self.chat_entry = tk.Entry(self, width=45)
        self.chat_entry.insert(0, self.cfg.telegram_chat_id)
        self.chat_entry.pack()

        tk.Button(self, text="Save Telegram Config", command=self.save_telegram).pack(pady=5)

        # ===== Status =====
        self.status_label = tk.Label(self, text="🔴 Disconnected")
        self.status_label.pack(pady=5)

        # ===== Chat Box =====
        tk.Label(self, text="Chat with Controller").pack()
        self.chat_box = tk.Text(self, height=10, width=50, state=tk.DISABLED)
        self.chat_box.pack(pady=5)

        self.msg_entry = tk.Entry(self, width=40)
        self.msg_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(self, text="Send", command=self.send_chat).pack(side=tk.LEFT)

        # ===== WebSocket Client =====
        self.client = WebSocketClient(
            on_chat_callback=self.display_chat,
            on_status_callback=self.update_status
        )

        threading.Thread(target=self.run_ws, daemon=True).start()

        # ===== System Tray =====
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.icon = None
        self.tray_thread = threading.Thread(target=self.create_tray_icon, daemon=True)
        self.tray_thread.start()

    def run_ws(self):
        self.client.connect()

    def revoke(self):
        """Revoke device id + remove from startup"""
        self.cfg.revoke_device_id()
        self.device_label.config(text=self.cfg.device_id)
        remove_from_startup()
        self.status_label.config(text="⚠️ Device ID revoked, removed from startup")

    def save_telegram(self):
        self.cfg.telegram_token = self.token_entry.get()
        self.cfg.telegram_chat_id = self.chat_entry.get()
        self.cfg.save()
        self.status_label.config(text="💾 Saved Telegram config")

    def update_status(self, connected: bool):
        color = "🟢 Connected" if connected else "🔴 Disconnected"
        self.status_label.config(text=color)

    def display_chat(self, msg: str):
        """Hiển thị tin nhắn và tự bật app nếu đang minimize"""
        self.chat_box.config(state=tk.NORMAL)
        self.chat_box.insert(tk.END, msg + "\n")
        self.chat_box.config(state=tk.DISABLED)
        self.chat_box.see(tk.END)

        # 👉 Kiểm tra nếu đang minimize → restore
        try:
            if self.state() == 'iconic':
                self.deiconify()
            self.lift()
            self.focus_force()
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"⚠️ Restore window failed: {e}")

    def send_chat(self):
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.client.send_chat(text)
        self.msg_entry.delete(0, tk.END)
        self.display_chat(f"You: {text}")

    # ================== TRAY ICON ==================

    def minimize_to_tray(self):
        """Ẩn cửa sổ và hiển thị icon trong tray"""
        self.withdraw()
        if not self.icon:
            self.create_tray_icon()

    def create_tray_icon(self):
        """Tạo icon nhỏ trong khay hệ thống"""
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 63, 63), fill=(30, 144, 255))
        draw.text((20, 20), "A", fill="white")

        def on_show(icon, item):
            self.deiconify()
            self.lift()
            self.focus_force()

        def on_exit(icon, item):
            icon.stop()
            self.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("Hiện cửa sổ", on_show),
            pystray.MenuItem("Thoát", on_exit)
        )

        self.icon = pystray.Icon("agent", image, "Windows Agent", menu)
        self.icon.run()

    def copy_device_id(self):
        """Copy Device ID to clipboard"""
        self.clipboard_clear()
        self.clipboard_append(self.cfg.device_id)
        self.update()  # keeps clipboard after closing
        messagebox.showinfo("Copied", "Device ID copied to clipboard!")

    def open_config_folder(self):
        """Open folder containing config.json (create if missing)"""
        config_path = os.path.abspath(self.cfg.config_path) if hasattr(self.cfg, "config_path") else None
        if not config_path:
            messagebox.showerror("Error", "Config path not found in Config class.")
            return
        folder = os.path.dirname(config_path)
        os.makedirs(folder, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open folder:\n{e}")
