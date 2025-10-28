import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import ctypes
from PIL import Image, ImageDraw
import pystray

from core.telegram_service import TelegramService
from core.tts_service import synthesize_and_play
if sys.platform == "win32":
    import winreg
else:
    winreg = None

from core.config import Config
from core.websocket_client import WebSocketClient


def remove_from_startup():
    try:
        key = winreg.HKEY_CURRENT_USER
        key_value = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        open_key = winreg.OpenKey(key, key_value, 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteValue(open_key, "WindowManagerAgent")
        winreg.CloseKey(open_key)
    except Exception:
        pass


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.title("Windows Remote Agent")
        self.geometry("550x800")
        self.minsize(520, 500)
        self.configure(bg="#f5f6fa")
        self.telegram = TelegramService()
        # ===== Style =====
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabel", background="#f5f6fa", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), foreground="#0066cc")
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=5)

        container = ttk.Frame(self, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        # ===== Top Info (shortened) =====
        info_frame = ttk.LabelFrame(container, text="Device Info")
        info_frame.pack(fill=tk.X, pady=5)

        ttk.Label(info_frame, text="Device ID:").pack(anchor="w")
        self.device_label = ttk.Label(info_frame, text=self.cfg.device_id, wraplength=400)
        self.device_label.pack(anchor="w", pady=(0, 4))

        btn_row = ttk.Frame(info_frame)
        btn_row.pack()
        ttk.Button(btn_row, text="📋 Copy ID", width=14, command=self.copy_device_id).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="📂 Open Folder", width=14, command=self.open_config_folder).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="❌ Revoke", width=14, command=self.revoke).pack(side=tk.LEFT, padx=3)


        # ===== Telegram Config (compact) =====
        tg_frame = ttk.LabelFrame(container, text="Telegram Config")
        tg_frame.pack(fill=tk.X, pady=5)

        ttk.Label(tg_frame, text="Token:").pack(anchor="w")
        self.token_entry = ttk.Entry(tg_frame, width=45)
        self.token_entry.insert(0, self.cfg.telegram_token)
        self.token_entry.pack(anchor="w", pady=2)

        ttk.Label(tg_frame, text="Chat ID:").pack(anchor="w")
        self.chat_entry = ttk.Entry(tg_frame, width=45)
        self.chat_entry.insert(0, self.cfg.telegram_chat_id)
        self.chat_entry.pack(anchor="w", pady=2)

        ttk.Button(tg_frame, text="💾 Save Config", command=self.save_telegram).pack(pady=4)

        # ===== Status =====
        self.status_label = ttk.Label(container, text="🔴 Disconnected", foreground="red", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(pady=(5, 10))

        # ===== Chat Section =====
        chat_frame = ttk.LabelFrame(container, text="Chat with Controller")
        chat_frame.pack(fill=tk.BOTH, expand=True)

        # Chat box
        self.chat_box = tk.Text(chat_frame, height=8, wrap=tk.WORD,
                                bg="#1e1e1e", fg="#e0e0e0", font=("Consolas", 10),
                                relief=tk.FLAT, padx=10, pady=6, state=tk.DISABLED)
        self.chat_box.pack(fill=tk.BOTH, expand=True, pady=(5, 2))

        # Input row (fixed bottom)
        input_row = ttk.Frame(chat_frame)
        input_row.pack(fill=tk.X, pady=4)
        self.msg_entry = ttk.Entry(input_row)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        ttk.Button(input_row, text="Send ➤", command=self.send_chat).pack(side=tk.LEFT, padx=4)
        self.msg_entry.bind("<Return>", self._on_enter)

        # ===== WebSocket =====
        self.client = WebSocketClient(
            on_chat_callback=self.display_chat,
            on_status_callback=self.update_status
        )
        threading.Thread(target=self.run_ws, daemon=True).start()

        # ===== Tray =====
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.icon = None
        threading.Thread(target=self.create_tray_icon, daemon=True).start()

    # ========== Core Functions ==========

    def run_ws(self):
        self.client.connect()

    def revoke(self):
        self.cfg.revoke_device_id()
        self.device_label.config(text=self.cfg.device_id)
        remove_from_startup()
        self.status_label.config(text="⚠️ Device ID revoked", foreground="orange")

    def save_telegram(self):
        self.cfg.telegram_token = self.token_entry.get()
        self.cfg.telegram_chat_id = self.chat_entry.get()
        self.cfg.save()
        messagebox.showinfo("Saved", "Telegram config saved!\nApp will restart.")
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def update_status(self, connected: bool):
        self.status_label.config(
            text="🟢 Connected" if connected else "🔴 Disconnected",
            foreground="green" if connected else "red"
        )

    # ========== Chat Logic ==========

    def display_chat(self, msg: str):
        self.chat_box.config(state=tk.NORMAL)
        tag = "selfmsg" if msg.startswith("You:") else "servermsg"
        self.chat_box.insert(tk.END, msg + "\n", tag)
        self.chat_box.tag_config("selfmsg", foreground="#00aaff")
        self.chat_box.tag_config("servermsg", foreground="#90ee90")
        self.chat_box.config(state=tk.DISABLED)
        self.chat_box.see(tk.END)

        # Khi có tin nhắn mới từ server → đọc bằng TTS
        if not msg.startswith("You:"):
            text_to_speak = msg.split(":", 1)[1]
            threading.Thread(
                target=lambda: synthesize_and_play(text_to_speak, voice_gender="FEMALE"),
                daemon=True
            ).start()

        try:
            if self.state() == 'iconic':
                self.deiconify()
            self.lift()
            self.focus_force()
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _on_enter(self, event):
        """Gửi tin nhắn khi nhấn Enter"""
        self.send_chat()
        return "break"  # Ngăn xuống dòng trong Entry
    
    def send_chat(self):
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.client.send_chat(text)
        self.msg_entry.delete(0, tk.END)
        self.display_chat(f"You: {text}")
        
        # Gửi qua Telegram ở thread phụ để không chặn UI
        threading.Thread(
            target=lambda: self.telegram.send_message(f"Agent was sent message: {text}"),
            daemon=True
        ).start()

    # ========== Tray ==========
    def minimize_to_tray(self):
        self.withdraw()
        if not self.icon:
            self.create_tray_icon()

    def create_tray_icon(self):
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 63, 63), fill=(30, 144, 255))
        draw.text((22, 20), "A", fill="white")

        def on_show(icon, item):
            self.deiconify()
            self.lift()
            self.focus_force()

        def on_exit(icon, item):
            icon.stop()
            self.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("Show Window", on_show),
            pystray.MenuItem("Exit", on_exit)
        )
        self.icon = pystray.Icon("agent", image, "Windows Agent", menu)
        self.icon.run()

    # ========== Helpers ==========
    def copy_device_id(self):
        self.clipboard_clear()
        self.clipboard_append(self.cfg.device_id)
        self.update()
        messagebox.showinfo("Copied", "Device ID copied!")

    def open_config_folder(self):
        path = os.path.abspath(getattr(self.cfg, "config_path", ""))
        if not path:
            messagebox.showerror("Error", "Config path not found.")
            return
        folder = os.path.dirname(path)
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
