import os
import sys

# Base directory — при запуске как .exe берём папку рядом с .exe,
# при запуске как скрипт — папку скрипта
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Server
HOST = "0.0.0.0"
PORT = 5000

# Files
HISTORY_FILE       = os.path.join(BASE_DIR, "clipboard_history.json")
CLIPBOARD_IMG_FILE = os.path.join(BASE_DIR, "clipboard_image.png")
CLIPBOARD_FILE_DAT = os.path.join(BASE_DIR, "clipboard_file.dat")

# Настройки
DEFAULT_AUTO_TO_PC        = True
DEFAULT_AUTO_TO_PHONE     = True
DEFAULT_NOTIFY_ON_RECEIVE = True
DEFAULT_AUTOSTART         = False
