# main.py
import asyncio
import os
import sys
if sys.platform == "win32":
    import winreg
else:
    winreg = None
from ui.main_window import MainWindow

def add_to_startup(file_path=None):
    """Thêm app vào startup Windows (tự chạy khi khởi động)"""
    try:
        if file_path is None:
            file_path = os.path.realpath(sys.argv[0])
        key = winreg.HKEY_CURRENT_USER
        key_value = r"Software\Microsoft\Windows\CurrentVersion\Run"
        open_key = winreg.OpenKey(key, key_value, 0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(open_key, "WindowManagerAgent", 0, winreg.REG_SZ, file_path)
        winreg.CloseKey(open_key)
        print(f"✅ Added to startup: {file_path}")
    except Exception as e:
        print(f"⚠️ Failed to add to startup: {e}")
        
if __name__ == "__main__":
    add_to_startup()
    app = MainWindow()
    app.mainloop()
