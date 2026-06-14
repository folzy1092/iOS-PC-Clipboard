import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Server (
HOST = "0.0.0.0"
PORT = 5000

# Files
HISTORY_FILE       = os.path.join(BASE_DIR, "clipboard_history.json")
CLIPBOARD_IMG_FILE = os.path.join(BASE_DIR, "clipboard_image.png")
CLIPBOARD_FILE_DAT = os.path.join(BASE_DIR, "clipboard_file.dat")

# --- НАСТРОЙКИ ПО УМОЛЧАНИЮ ---
DEFAULT_AUTO_TO_PC        = True
DEFAULT_AUTO_TO_PHONE     = True
DEFAULT_NOTIFY_ON_RECEIVE = True

# Если хочешь, чтобы при первом запуске (если нет ключа в реестре) 
# автозагрузка включалась сама, поставь True:
DEFAULT_AUTOSTART         = False