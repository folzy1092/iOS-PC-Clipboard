from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import time
import pyperclip
import threading
import webbrowser
import pystray
import subprocess
import sys
from PIL import Image, ImageDraw, ImageGrab
import json
import os
import io
import base64
import hashlib
import win32clipboard
import winreg
import config
import re


if getattr(sys, 'frozen', False):
    # Если запущен как .exe, используем временную папку PyInstaller
    _PROJECT_DIR = sys._MEIPASS
else:
    # Если запущен как скрипт, используем текущую папку
    _PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


app = Flask(__name__, static_folder=_PROJECT_DIR, static_url_path='')
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

HISTORY_FILE = config.HISTORY_FILE

_state_lock = threading.Lock()
_tray_icon  = None

state = {
    "pc_text":           "",
    "phone_text":        "",
    "to_phone_text":     "",
    "updated_at":        0,
    "auto_to_pc":        config.DEFAULT_AUTO_TO_PC,
    "auto_to_phone":     config.DEFAULT_AUTO_TO_PHONE,
    "history":           [],
    "requests":          [],
    "last_type":         "text",
    "pc_image":          None,
    "phone_image":       None,
    "last_img_hash":     None,
    "last_set_img_hash": None,
    "last_event":        "",
    "notify_on_receive": config.DEFAULT_NOTIFY_ON_RECEIVE,
}


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                state['history']           = data.get('history',      [])[:50]
                state['requests']          = data.get('requests',     [])[:50]
                state['auto_to_pc']        = data.get('auto_to_pc',        config.DEFAULT_AUTO_TO_PC)
                state['auto_to_phone']     = data.get('auto_to_phone',     config.DEFAULT_AUTO_TO_PHONE)
                state['notify_on_receive'] = data.get('notify_on_receive', config.DEFAULT_NOTIFY_ON_RECEIVE)
        except Exception:
            state['history']  = []
            state['requests'] = []


def save_history():
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'history':           state['history'][:50],
                'requests':          state['requests'][:50],
                'auto_to_pc':        state['auto_to_pc'],
                'auto_to_phone':     state['auto_to_phone'],
                'notify_on_receive': state['notify_on_receive'],
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def add_to_history(text, source, content_type="text"):
    label = text if content_type == "text" else "[изображение]"
    if not label or not label.strip():
        return
    with _state_lock:
        if state['history'] and state['history'][0].get('text') == label:
            return
        state['history'].insert(0, {
            'text':   label,
            'time':   time.time(),
            'source': source,
            'type':   content_type,
        })
        if len(state['history']) > 50:
            state['history'] = state['history'][:50]
    save_history()


def add_request(action, content_type, details=""):
    with _state_lock:
        state['requests'].insert(0, {
            'action':  action,
            'type':    content_type,
            'time':    time.time(),
            'details': details,
        })
        if len(state['requests']) > 50:
            state['requests'] = state['requests'][:50]
    save_history()


def img_to_b64(pil_img):
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def b64_hash(b64str):
    return hashlib.md5(b64str.encode()).hexdigest()


def get_clipboard_image_b64():
    try:
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            return img_to_b64(img)
    except Exception:
        pass
    return None


def set_clipboard_text_win(text):
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception as e:
        print(f"[text] Ошибка записи текста в буфер: {e}")


def set_clipboard_image_win(b64_data):
    try:
        img_bytes = base64.b64decode(b64_data)
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            buf = io.BytesIO()
            img.save(buf, 'BMP')
            bmp = buf.getvalue()[14:]
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp)
            win32clipboard.CloseClipboard()
            state['last_set_img_hash'] = b64_hash(b64_data)
            print("[img] Изображение скопировано в буфер Windows")
        except Exception:
            with open(config.CLIPBOARD_FILE_DAT, "wb") as f:
                f.write(img_bytes)
            print(f"[file] Получен файл, сохранен как {config.CLIPBOARD_FILE_DAT}")
    except Exception as e:
        print(f"[img] Ошибка записи в буфер: {e}")


def emit_state():
    payload = {k: v for k, v in state.items()
               if k not in ('pc_image', 'phone_image', 'last_set_img_hash')}
    payload['has_pc_image']        = state['pc_image']    is not None
    payload['has_phone_image']     = state['phone_image'] is not None
    payload['last_phone_img_hash'] = b64_hash(state['phone_image']) if state['phone_image'] else None
    socketio.emit('state_update', payload)


def tray_notify(message, title="Clipboard"):
    if _tray_icon and state.get('notify_on_receive', True):
        try:
            _tray_icon.notify(message, title)
        except Exception:
            pass


_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "ClipboardServer"


def is_autostart_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _REG_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart(enable: bool):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            if getattr(sys, 'frozen', False):
                # .exe — sys.executable и есть наш бинарь
                cmd = f'"{sys.executable}"'
            else:
                script_path  = os.path.abspath(__file__)
                pythonw_path = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                cmd = f'"{pythonw_path}" "{script_path}"'
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, _REG_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[autostart] Ошибка: {e}")


@app.route('/')
def index():
    return send_from_directory(_PROJECT_DIR, 'index.html')

def decode_single_b64_chunk(b64_str):
    if not b64_str.strip():
        return ""
    try:
        clean_b64 = b64_str.strip()
        padded_data = clean_b64 + '=' * (-len(clean_b64) % 4)
        raw_bytes = base64.b64decode(padded_data, validate=True)
    except Exception:
        return b64_str.strip()

    # Строгий UTF-8 без игнорирования — нормальный текст и кириллица пройдут здесь
    try:
        return raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        pass

    # Бинарные данные (iOS plist, bookmark, RTF...) — ищем URL прямо в байтах
    url_match = re.search(rb'https?://[^\x00-\x1f\x7f-\x9f\s<>"{}|\\^`]+', raw_bytes)
    if url_match:
        return url_match.group(0).decode('ascii', errors='ignore')

    # Фолбек: mojibake-кириллица через latin1->utf-8
    try:
        fixed = raw_bytes.decode('latin1').encode('latin1').decode('utf-8', errors='ignore')
        if any(chr(1040) <= c <= chr(1103) for c in fixed):
            return fixed
    except Exception:
        pass

    # Последний фолбек
    return raw_bytes.decode('utf-8', errors='ignore')


def decode_smart_clipboard(raw_data):
    if not raw_data:
        return ""

    if isinstance(raw_data, str):
        chunks = [c.strip() for c in raw_data.split('\n') if c.strip()]
        
        if len(chunks) > 1:
            processed_chunks = []
            for chunk in chunks:
                res = decode_single_b64_chunk(chunk)
                if res:
                    processed_chunks.append(res)
            return "\n\n".join(processed_chunks)
        else:
            return decode_single_b64_chunk(raw_data)
            
    return str(raw_data)


def strip_rtf(text):
    stripped = text.strip()
    if not stripped.startswith('{\\rtf'):
        return text
    clean = re.sub(r'\\par\b\s?', '\n', stripped)
    clean = re.sub(r'\\line\b\s?', '\n', clean)
    clean = re.sub(r'\\u(\d+) ?', lambda m: chr(int(m.group(1))), clean)
    clean = re.sub(r'\{[^{}]*\}', '', clean)
    clean = re.sub(r'\\[a-zA-Z0-9\-]+\s?', '', clean)
    clean = re.sub(r'[{}\\]', '', clean)
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = '\n'.join(line.strip() for line in clean.split('\n'))
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
    return clean if clean else text


@app.route('/update', methods=['POST'])
def update():
    req_data = request.get_json(silent=True)
    if not req_data or 'data' not in req_data:
        return jsonify({"ok": False, "error": "No data"}), 400

    raw_data = str(req_data['data'])
    explicit_type = req_data.get('type')

    if explicit_type == "image" or explicit_type is None:
        try:
            decoded_bytes = base64.b64decode(raw_data, validate=True)
            img = Image.open(io.BytesIO(decoded_bytes))
            img.verify()

            with open(config.CLIPBOARD_IMG_FILE, "wb") as f:
                f.write(decoded_bytes)
            state['phone_image'] = base64.b64encode(decoded_bytes).decode('utf-8')
            state['phone_text']  = ""
            state['last_type']   = "image"
            state['updated_at']  = time.time()
            state['last_event']  = 'phone_sent_img'

            add_to_history("", 'phone', 'image')
            add_request('received', 'image', 'Изображение получено с iPhone')
            emit_state()
            tray_notify("Получено изображение с iPhone")

            if state['auto_to_pc']:
                subprocess.run(["powershell", "-Command",
                                f"Set-Clipboard -Path '{config.CLIPBOARD_IMG_FILE}'"])
            return jsonify({"ok": True, "type": "image"})

        except Exception:
            if explicit_type == "image":
                return jsonify({"ok": False, "error": "Invalid image data"}), 400

    text_content = decode_smart_clipboard(raw_data)
    text_content = strip_rtf(text_content)
    text_content = ''.join(
        ch for ch in text_content
        if ch == '\n' or ch == '\t' or (ord(ch) >= 0x20)
    ).strip()

    if not text_content:
        return jsonify({"ok": False, "error": "Empty text"}), 400

    state['phone_text'] = text_content
    state['last_type']  = "text"
    state['updated_at'] = time.time()
    state['last_event'] = 'phone_sent'

    add_to_history(text_content, 'phone', 'text')
    add_request('received', 'text',
                f'Текст: {text_content[:50]}{"..." if len(text_content) > 50 else ""}')

    if state['auto_to_pc']:
        set_clipboard_text_win(text_content)

    emit_state()
    tray_notify(f"Получено с iPhone: {text_content[:40]}")
    return jsonify({"ok": True, "type": "text", "content": text_content[:50]})


@app.route('/get-phone')
def get_phone():
    if state['pc_image'] and state['last_type'] == "image":
        state['last_event'] = 'phone_fetched_img'
        add_request('sent', 'image', 'ПК → iPhone: изображение из буфера')
        emit_state()
        return jsonify({"type": "image", "data": state['pc_image']})

    current_text = state['pc_text'] if state['pc_text'] else "Буфер обмена пуст"
    if state['pc_text']:
        state['last_event'] = 'phone_fetched'
        add_request('sent', 'text',
                    f'ПК → iPhone: {current_text[:40]}{"..." if len(current_text) > 40 else ""}')
        emit_state()
    return jsonify({"type": "text", "data": current_text})


@app.route('/get-image')
def get_image():
    return jsonify({"image": state['pc_image']})


@app.route('/get-phone-image')
def get_phone_image():
    return jsonify({"image": state['phone_image']})


@socketio.on('connect')
def handle_connect():
    emit_state()


@socketio.on('toggle_settings')
def handle_toggle(data):
    if 'auto_to_pc'    in data: state['auto_to_pc']    = bool(data['auto_to_pc'])
    if 'auto_to_phone' in data: state['auto_to_phone'] = bool(data['auto_to_phone'])
    save_history()
    emit_state()


@socketio.on('manual_send_to_phone')
def handle_manual_send(data):
    if 'text' in data:
        text = str(data['text'])
        state['pc_text']    = text
        state['pc_image']   = None
        state['last_type']  = "text"
        state['updated_at'] = time.time()
        state['last_event'] = 'panel_sent'
        add_to_history(text, 'pc', 'text')
        emit_state()


@socketio.on('clear_history')
def handle_clear_history():
    with _state_lock:
        state['history'] = []
    save_history()
    emit_state()


@socketio.on('clear_requests')
def handle_clear_requests():
    with _state_lock:
        state['requests'] = []
    save_history()
    emit_state()


def monitor_pc_clipboard_text():
    last_text = ""
    try:
        last_text = pyperclip.paste()
    except Exception:
        pass

    while True:
        time.sleep(0.3)
        if not state['auto_to_phone']:
            continue
        try:
            cur_text = pyperclip.paste()
            if (cur_text and cur_text != last_text
                    and cur_text != state['phone_text']):
                state['pc_text']    = cur_text
                state['pc_image']   = None
                state['last_type']  = "text"
                state['updated_at'] = time.time()
                state['last_event'] = 'pc_copied'
                add_to_history(cur_text, 'pc', 'text')
                emit_state()
                last_text = cur_text
        except Exception:
            pass


def monitor_pc_clipboard_image():
    while True:
        time.sleep(1.5)
        if not state['auto_to_phone']:
            continue
        try:
            img_b64 = get_clipboard_image_b64()
            if img_b64:
                img_hash = b64_hash(img_b64)
                if (img_hash != state.get('last_set_img_hash')
                        and img_hash != state.get('last_img_hash')):
                    state['pc_image']      = img_b64
                    state['pc_text']       = ""
                    state['last_type']     = "image"
                    state['last_img_hash'] = img_hash
                    state['updated_at']    = time.time()
                    state['last_event']    = 'pc_copied_img'
                    add_to_history("", 'pc', 'image')
                    emit_state()
        except Exception:
            pass


def create_tray_image():
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.rounded_rectangle([8, 8, 56, 56], radius=12, fill=(136, 136, 255, 255))
    dc.rectangle([20, 20, 44, 26], fill=(255, 255, 255, 255))
    dc.rectangle([20, 32, 44, 36], fill=(255, 255, 255, 255))
    dc.rectangle([20, 42, 36, 46], fill=(255, 255, 255, 255))
    return image


def run_server():
    socketio.run(app, host=config.HOST, port=config.PORT, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    load_history()
    if config.DEFAULT_AUTOSTART and not is_autostart_enabled():
            set_autostart(True)
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=monitor_pc_clipboard_text,  daemon=True).start()
    threading.Thread(target=monitor_pc_clipboard_image, daemon=True).start()

    def open_browser(icon, item):
        webbrowser.open('http://localhost:5000')

    def on_exit(icon, item):
        icon.stop()
        os._exit(0)

    def toggle(key):
        state[key] = not state[key]
        save_history()
        emit_state()

    def restart_app(icon, item):
        if getattr(sys, 'frozen', False):
            args = [sys.executable]
        else:
            script_path  = os.path.abspath(__file__)
            pythonw_path = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            args = [pythonw_path, script_path]
        icon.stop()
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os._exit(0)

    def toggle_autostart(icon, item):
        set_autostart(not is_autostart_enabled())

    def quick_to_phone(icon, item):
        try:
            t = pyperclip.paste()
            if t:
                state['pc_text']    = t
                state['pc_image']   = None
                state['last_type']  = "text"
                state['updated_at'] = time.time()
                add_to_history(t, 'pc', 'text')
                emit_state()
        except Exception:
            pass

    def quick_from_phone(icon, item):
        if state['phone_text']:
            try:
                set_clipboard_text_win(state['phone_text'])
            except Exception:
                pass

    menu = pystray.Menu(
        pystray.MenuItem(
            "Авто: iPhone → ПК",
            lambda i, it: toggle("auto_to_pc"),
            checked=lambda it: state['auto_to_pc'],
        ),
        pystray.MenuItem(
            "Авто: ПК → iPhone",
            lambda i, it: toggle("auto_to_phone"),
            checked=lambda it: state['auto_to_phone'],
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Открыть панель",              open_browser),
        pystray.MenuItem("ПК → iPhone вручную",         quick_to_phone),
        pystray.MenuItem("iPhone → буфер ПК вручную",   quick_from_phone),
        pystray.MenuItem(
            "Уведомления при получении",
            lambda i, it: toggle("notify_on_receive"),
            checked=lambda it: state['notify_on_receive'],
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Автозагрузка с Windows",
            toggle_autostart,
            checked=lambda it: is_autostart_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Перезапустить", restart_app),
        pystray.MenuItem("Выход",         on_exit),
    )

    icon = pystray.Icon("ClipboardServer", create_tray_image(), menu=menu)
    icon.title = "Clipboard Server"
    _tray_icon = icon
    icon.run()