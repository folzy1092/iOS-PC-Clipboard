from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO
import time
import pyperclip
import threading
import webbrowser
import pystray
import subprocess
from PIL import Image, ImageDraw, ImageGrab
import json
import os
import io
import base64
import hashlib
import urllib.parse
import win32clipboard
import re
import config

app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

HISTORY_FILE = config.HISTORY_FILE

state = {
    "pc_text":          "",
    "phone_text":       "",
    "updated_at":       0,
    "auto_to_pc":       config.DEFAULT_AUTO_TO_PC,
    "auto_to_phone":    config.DEFAULT_AUTO_TO_PHONE,
    "history":          [],
    "requests":         [],
    "last_type":        "text",
    "pc_image":         None,
    "phone_image":      None,
    "last_img_hash":    None,
    "last_set_img_hash": None,
}


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                state['history'] = data.get('history', [])[:50]
                state['requests'] = data.get('requests', [])[:50]
        except Exception:
            state['history'] = []
            state['requests'] = []

def save_history():
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'history': state['history'][:50],
                'requests': state['requests'][:50]
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def add_to_history(text, source, content_type="text"):
    label = text if content_type == "text" else "[изображение]"
    if not label or not label.strip():
        return
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
    state['requests'].insert(0, {
        'action': action,
        'type': content_type,
        'time': time.time(),
        'details': details
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
    payload['has_pc_image']       = state['pc_image']    is not None
    payload['has_phone_image']    = state['phone_image'] is not None
    payload['last_phone_img_hash'] = b64_hash(state['phone_image']) if state['phone_image'] else None
    socketio.emit('state_update', payload)


PAGE = """<!DOCTYPE html>
<html>
<head>
  <title>Clipboard</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f0f17; color: #e0e0e0; font-family: 'Courier New', monospace;
      min-height: 100vh; padding: 20px;
    }
    .container { 
      display: grid; 
      grid-template-columns: 1fr 1fr 1fr; 
      gap: 20px; 
      height: calc(100vh - 40px);
    }
    @media (max-width: 1400px) {
      .container { grid-template-columns: 1fr 1fr; }
      .column:nth-child(3) { grid-column: 1 / -1; }
    }
    @media (max-width: 900px) {
      .container { grid-template-columns: 1fr; }
      .column { grid-column: 1 / -1 !important; }
    }
    .column { 
      background: #1a1a2e; 
      border: 1px solid #2a2a4a; 
      border-radius: 12px; 
      padding: 24px;
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
    }
    h2 { font-size: 18px; color: #8888ff; margin-bottom: 16px; }
    h3 { font-size: 16px; color: #8888ff; margin-bottom: 12px; margin-top: 16px; }
    h3:first-of-type { margin-top: 0; }
    textarea { width: 100%; background: #0f0f17; color: #e0e0e0; border: 1px solid #2a2a4a; border-radius: 8px; padding: 12px; font-family: 'Courier New', monospace; font-size: 14px; resize: vertical; }
    #text { height: 150px; }
    #sendText { height: 90px; }
    .buttons { display: flex; gap: 10px; margin-top: 12px; }
    button { flex: 1; padding: 10px; border: none; border-radius: 7px; cursor: pointer; font-size: 14px; font-family: monospace; transition: background 0.15s; }
    .btn-copy  { background: #3a3a7a; color: #fff; } .btn-copy:hover  { background: #5a5aaa; }
    .btn-send  { background: #7a3a3a; color: #fff; } .btn-send:hover  { background: #aa5a5a; }
    .btn-save  { background: #2a4a2a; color: #aaffaa; } .btn-save:hover { background: #3a6a3a; }
    #status { margin-top: 15px; font-size: 12px; color: #888; text-align: center; }
    .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #444; margin-right: 6px; vertical-align: middle; }
    .dot.live { background: #44ff88; animation: pulse 2s infinite; }
    .dot.dead { background: #ff4444; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
    .section { margin-top: 20px; padding-top: 20px; border-top: 1px solid #2a2a4a; }
    .section:first-of-type { margin-top: 0; padding-top: 0; border-top: none; }
    .toggle-container { display: flex; align-items: center; justify-content: space-between; background: #0f0f17; border: 1px solid #2a2a4a; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
    .toggle-label { color: #b0b0b0; font-size: 13px; }
    .toggle-switch { position: relative; display: inline-block; width: 46px; height: 22px; }
    .toggle-switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #2a2a4a; transition: .2s; border-radius: 22px; }
    .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: .2s; border-radius: 50%; }
    input:checked + .slider { background-color: #44ff88; }
    input:checked + .slider:before { transform: translateX(24px); }
    .history-item { background: #0f0f17; border: 1px solid #2a2a4a; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-size: 13px; }
    .history-item .time { color: #888; font-size: 11px; margin-bottom: 4px; }
    .history-item .source { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 8px; }
    .history-item .source.pc { background: #3a3a7a; color: #fff; }
    .history-item .source.phone { background: #7a3a3a; color: #fff; }
    .history-item .content { color: #e0e0e0; word-break: break-word; white-space: pre-wrap; }
    .history-item .content.img-entry { color: #88ff88; }
    .history-container { overflow-y: auto; flex: 1; scrollbar-width: none; -ms-overflow-style: none; }
    .history-container::-webkit-scrollbar { width: 0; height: 0; }
    .btn-clear { background: #444; color: #fff; padding: 4px 10px; border: none; border-radius: 5px; cursor: pointer; font-size: 10px; font-family: monospace; margin-top: auto; flex: 0.05; }
    .btn-clear:hover { background: #666; }
    .img-preview { max-width: 100%; border-radius: 8px; border: 1px solid #2a2a4a; display: block; margin-top: 8px; }
    .img-label { font-size: 12px; color: #888; margin-bottom: 4px; }
    a.btn-save-link { display: block; text-align: center; padding: 10px; background: #2a4a2a; color: #aaffaa; border-radius: 7px; text-decoration: none; font-family: monospace; font-size: 14px; margin-top: 8px; }
    a.btn-save-link:hover { background: #3a6a3a; }
    .request-item { background: #0f0f17; border: 1px solid #2a2a4a; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-size: 13px; }
    .request-item .time { color: #888; font-size: 11px; margin-bottom: 4px; }
    .request-item .action { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; margin-right: 6px; font-weight: bold; }
    .request-item .action.sent { background: #7a3a3a; color: #fff; }
    .request-item .action.received { background: #3a7a3a; color: #fff; }
    .request-item .type { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; background: #3a3a7a; color: #fff; }
    .request-item .details { color: #b0b0b0; margin-top: 6px; font-size: 12px; }
  </style>
</head>
<body>
<div class="container">
  
  <!-- СТОЛБЕЦ 1: Управление и отправка -->
  <div class="column">
    <h2><span class="dot" id="dot"></span>📋 Clipboard Server</h2>

    <div class="toggle-container">
      <span class="toggle-label">🔄 Авто: iPhone ➔ буфер ПК</span>
      <label class="toggle-switch">
        <input type="checkbox" id="autoToPcToggle" {% if auto_to_pc %}checked{% endif %} onchange="updateToggles()">
        <span class="slider"></span>
      </label>
    </div>
    <div class="toggle-container" style="margin-bottom: 16px;">
      <span class="toggle-label">⚡ Авто: буфер ПК ➔ iPhone</span>
      <label class="toggle-switch">
        <input type="checkbox" id="autoToPhoneToggle" {% if auto_to_phone %}checked{% endif %} onchange="updateToggles()">
        <span class="slider"></span>
      </label>
    </div>

    <textarea id="text" readonly placeholder="Буфер пуст — отправь что-нибудь с iPhone"></textarea>
    <div class="buttons">
      <button class="btn-copy" onclick="manualCopy()">📋 Скопировать текст</button>
    </div>

    <div class="section">
      <h3>📤 Отправить текст на iPhone</h3>
      <textarea id="sendText" placeholder="Введи текст для отправки на iPhone..."></textarea>
      <div class="buttons" style="margin-top: 8px;">
        <button class="btn-send" onclick="sendToPhone()">⚡ Отправить на iPhone</button>
      </div>
    </div>

    <div id="phoneImgSection" class="section" style="display:none;">
      <h3>📱 Изображение с iPhone</h3>
      <img id="phoneImg" class="img-preview">
    </div>

    <div id="pcImgSection" class="section" style="display:none;">
      <h3>🖥️ Изображение из буфера ПК</h3>
      <div class="img-label">Последний скриншот / картинка скопированная на ПК</div>
      <img id="pcImg" class="img-preview">
      <a id="pcImgDownload" class="btn-save-link" download="clipboard.png">💾 Сохранить</a>
    </div>

    <div id="status" style="margin-top: auto; padding-top: 20px;">Подключение...</div>
  </div>

  <!-- СТОЛБЕЦ 2: История буфера обмена -->
  <div class="column">
    <h2>📜 История буфера обмена</h2>
    <div id="historyContainer" class="history-container"></div>
    <button class="btn-clear" onclick="clearHistory()">🗑️ Очистить историю</button>
  </div>

  <!-- СТОЛБЕЦ 3: История запросов с iPhone -->
  <div class="column">
    <h2>📱 История запросов с iPhone</h2>
    <div id="requestsContainer" class="history-container"></div>
    <button class="btn-clear" onclick="clearRequests()">🗑️ Очистить запросы</button>
  </div>

</div>

<script>
  const socket = io();
  let lastUpdated = 0;
  let requests = [];
  let lastPcImgHash = null;
  let lastPhoneImgHash = null;

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  
  socket.on('connect', () => {
    document.getElementById('dot').className = 'dot live';
    document.getElementById('status').textContent = '✅ Соединение установлено';
  });
  
  socket.on('disconnect', () => {
    document.getElementById('dot').className = 'dot dead';
    document.getElementById('status').textContent = '❌ Потеряно соединение с ПК';
  });
  
  socket.on('state_update', (d) => {
    const oldText = document.getElementById('text').value;
    const newText = d.phone_text || '';

    document.getElementById('text').value = newText;
    document.getElementById('autoToPcToggle').checked  = d.auto_to_pc;
    document.getElementById('autoToPhoneToggle').checked = d.auto_to_phone;

    updateHistory(d.history || []);
    
    if (d.requests) {
      requests = d.requests;
      updateRequests(requests);
    }

    if (d.has_phone_image) {
      const serverHash = d.last_phone_img_hash || null;
      if (serverHash && serverHash !== lastPhoneImgHash) {
        lastPhoneImgHash = serverHash;
        fetch('/get-phone-image').then(r => r.json()).then(r => {
          if (r.image) {
            document.getElementById('phoneImg').src = 'data:image/png;base64,' + r.image;
            document.getElementById('phoneImgSection').style.display = 'block';
          }
        });
      } else if (!serverHash) {
        fetch('/get-phone-image').then(r => r.json()).then(r => {
          if (r.image) {
            document.getElementById('phoneImg').src = 'data:image/png;base64,' + r.image;
            document.getElementById('phoneImgSection').style.display = 'block';
          }
        });
      }
    } else {
      lastPhoneImgHash = null;
      document.getElementById('phoneImgSection').style.display = 'none';
    }

    if (d.has_pc_image) {
      const serverHash = d.last_img_hash || null;
      if (serverHash && serverHash !== lastPcImgHash) {
        lastPcImgHash = serverHash;
        fetch('/get-image').then(r => r.json()).then(r => {
          if (r.image) {
            const src = 'data:image/png;base64,' + r.image;
            document.getElementById('pcImg').src = src;
            document.getElementById('pcImgDownload').href = src;
            document.getElementById('pcImgSection').style.display = 'block';
          }
        });
      }
    } else {
      lastPcImgHash = null;
      document.getElementById('pcImgSection').style.display = 'none';
    }

    if (d.updated_at !== lastUpdated && lastUpdated !== 0) {
      const isImg = d.last_type === 'image';
      document.title = isImg ? '🖼️ Новое изображение!' : '🔔 Новый текст!';
      setTimeout(() => document.title = 'Clipboard', 3000);
      if (d.auto_to_pc) {
        document.getElementById('status').textContent = isImg
          ? '✅ Изображение скопировано в буфер ПК!'
          : '✅ Python автоматически скопировал текст!';
      } else {
        document.getElementById('status').textContent = isImg ? '📥 Получено изображение' : '📥 Получен новый текст';
      }
    } else if (d.updated_at > 0 && !document.getElementById('status').textContent.includes('Скопировано')) {
      const t = new Date(d.updated_at * 1000).toLocaleTimeString('ru-RU');
      document.getElementById('status').textContent = '✅ Последнее обновление: ' + t;
    }
    lastUpdated = d.updated_at;
  });
  
  function updateHistory(history) {
    const container = document.getElementById('historyContainer');
    if (!history || history.length === 0) {
      container.innerHTML = '<div style="color: #888; text-align: center; padding: 20px;">История пуста</div>';
      return;
    }
    container.innerHTML = history.map(item => {
      const time    = new Date(item.time * 1000).toLocaleString('ru-RU');
      const srcCls  = item.source === 'pc' ? 'pc' : 'phone';
      const srcText = item.source === 'pc' ? 'ПК' : 'iPhone';
      const isImg   = item.type === 'image';
      const rawText = item.text || '';
      const preview = isImg ? '🖼️ изображение' : escapeHtml(rawText.length > 100 ? rawText.substring(0, 100) + '...' : rawText);
      return `
        <div class="history-item">
          <div class="time">${escapeHtml(time)}<span class="source ${srcCls}">${srcText}</span></div>
          <div class="content ${isImg ? 'img-entry' : ''}">${preview}</div>
        </div>`;
    }).join('');
  }
  
  function updateRequests(requests) {
    const container = document.getElementById('requestsContainer');
    if (!requests || requests.length === 0) {
      container.innerHTML = '<div style="color: #888; text-align: center; padding: 20px;">Нет запросов</div>';
      return;
    }
    container.innerHTML = requests.map(req => {
      const time = new Date(req.time * 1000).toLocaleString('ru-RU');
      const actionCls = req.action === 'sent' ? 'sent' : 'received';
      const actionText = req.action === 'sent' ? '📤 Отправлено' : '📥 Получено';
      const typeText = req.type === 'text' ? '📝 Текст' : '🖼️ Изображение';
      const details = req.details || '';
      return `
        <div class="request-item">
          <div class="time">${escapeHtml(time)}</div>
          <div><span class="action ${actionCls}">${actionText}</span><span class="type">${typeText}</span></div>
          ${details ? `<div class="details">${escapeHtml(details)}</div>` : ''}
        </div>`;
    }).join('');
  }

  function updateToggles() {
    const toPc    = document.getElementById('autoToPcToggle').checked;
    const toPhone = document.getElementById('autoToPhoneToggle').checked;
    socket.emit('toggle_settings', { auto_to_pc: toPc, auto_to_phone: toPhone });
    document.getElementById('status').textContent = '✅ Настройки обновлены';
  }

  function manualCopy() {
    const text = document.getElementById('text').value;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      document.getElementById('status').textContent = '✅ Скопировано в буфер ПК!';
    });
  }

  function sendToPhone() {
    const text = document.getElementById('sendText').value;
    if (!text) { document.getElementById('status').textContent = '⚠️ Введите текст'; return; }
    socket.emit('manual_send_to_phone', { text });
    document.getElementById('status').textContent = '✅ Текст отправлен на iPhone!';
    document.getElementById('sendText').value = '';
  }

  function clearHistory() {
    if (confirm('Очистить всю историю буфера обмена?')) {
      socket.emit('clear_history');
      document.getElementById('status').textContent = '🗑️ История очищена';
    }
  }
  
  function clearRequests() {
    if (confirm('Очистить всю историю запросов?')) {
      socket.emit('clear_requests');
      document.getElementById('status').textContent = '🗑️ История запросов очищена';
    }
  }
</script>
</body>
</html>"""


@app.route('/')
def index():
    return render_template_string(PAGE, auto_to_pc=state['auto_to_pc'], auto_to_phone=state['auto_to_phone'])


@app.route('/update', methods=['POST'])
def update():
    req_data = request.get_json(silent=True)
    if not req_data or 'data' not in req_data:
        return jsonify({"ok": False, "error": "No data"}), 400
    
    raw_data = str(req_data['data'])
    
    try:
        clean_base64 = re.sub(r'[^A-Za-z0-9+/=]', '', raw_data)
        decoded_bytes = base64.b64decode(clean_base64)
        
        img = Image.open(io.BytesIO(decoded_bytes))
        img.verify()
        
        with open(config.CLIPBOARD_IMG_FILE, "wb") as f: f.write(decoded_bytes)
        state['phone_image'] = base64.b64encode(decoded_bytes).decode('utf-8')
        state['last_type'] = "image"
        state['updated_at'] = time.time()
        
        add_request('received', 'image', 'Изображение получено с iPhone')
        emit_state()
        
        if state['auto_to_pc']:
            subprocess.run(["powershell", "-Command", f"Set-Clipboard -Path '{config.CLIPBOARD_IMG_FILE}'"])
        return jsonify({"ok": True, "type": "image"})
    
    except Exception:
        try:
            text_content = base64.b64decode(raw_data).decode('utf-8', errors='ignore')
            text_content = re.sub(r'\\[a-z0-9]+\s?', '', text_content)
            text_content = re.sub(r'\{.*?\}', '', text_content, flags=re.DOTALL)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            
        except Exception:
            text_content = raw_data
            
        state['phone_text'] = text_content
        state['last_type'] = "text"
        state['updated_at'] = time.time()
        add_to_history(text_content, 'phone', 'text')
        add_request('received', 'text', f'Текст: {text_content[:50]}{"..." if len(text_content) > 50 else ""}')
        if state['auto_to_pc']:
            set_clipboard_text_win(text_content)
        emit_state()
        
        return jsonify({"ok": True, "type": "text", "content": text_content[:50]})

@app.route('/get-phone')
def get_phone():
    if state['last_type'] == "image" and state['pc_image']:
        add_request('sent', 'image', 'Изображение отправлено на iPhone')
        emit_state()
        return jsonify({"type": "image", "data": state['pc_image']})
    
    current_text = state['pc_text'] if state['pc_text'] else "Буфер обмена пуст"
    if state['pc_text']:
        add_request('sent', 'text', f'{current_text[:40]}{"..." if len(current_text) > 40 else ""}')
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
    emit_state()


@socketio.on('manual_send_to_phone')
def handle_manual_send(data):
    if 'text' in data:
        state['phone_text']  = str(data['text'])
        state['phone_image'] = None
        state['last_type']   = "text"
        state['updated_at']  = time.time()
        add_to_history(str(data['text']), 'phone', 'text')
        add_request('sent', 'text', f'Текст отправлен вручную: {str(data["text"])[:50]}{"..." if len(str(data["text"])) > 50 else ""}')
        emit_state()


@socketio.on('clear_history')
def handle_clear_history():
    state['history'] = []
    save_history()
    emit_state()


@socketio.on('clear_requests')
def handle_clear_requests():
    state['requests'] = []
    save_history()
    emit_state()


def monitor_pc_clipboard():
    last_text = ""
    try: last_text = pyperclip.paste()
    except Exception: pass

    while True:
        time.sleep(0.5)
        if not state['auto_to_phone']:
            continue

        try:
            cur_text = pyperclip.paste()
            if cur_text and cur_text != last_text and cur_text != state['phone_text']:
                state['pc_text']   = cur_text
                state['pc_image']  = None
                state['last_type'] = "text"
                state['updated_at'] = time.time()
                add_to_history(cur_text, 'pc', 'text')
                emit_state()
            last_text = cur_text
        except Exception:
            pass

        try:
            img_b64 = get_clipboard_image_b64()
            if img_b64:
                img_hash = b64_hash(img_b64)
                if img_hash != state.get('last_set_img_hash') and img_hash != state.get('last_img_hash'):
                    state['pc_image']     = img_b64
                    state['pc_text']      = ""
                    state['last_type']    = "image"
                    state['last_img_hash'] = img_hash
                    state['updated_at']   = time.time()
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

    threading.Thread(target=run_server,           daemon=True).start()
    threading.Thread(target=monitor_pc_clipboard, daemon=True).start()

    def open_browser(icon, item):      webbrowser.open('http://localhost:5000')
    def on_exit(icon, item):           icon.stop(); os._exit(0)
    def toggle(key):                   state[key] = not state[key]; emit_state()

    def restart_app(icon, item):
        # Запускаем новый процесс перед остановкой
        script_path = os.path.abspath(__file__)
        subprocess.Popen(['pythonw', script_path],
                        shell=True,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        # Даем время на запуск нового процесса
        time.sleep(0.5)
        icon.stop()
        os._exit(0)

    def quick_to_phone(icon, item):
        try:
            t = pyperclip.paste()
            if t:
                state['phone_text'] = t; state['pc_text'] = t
                state['phone_image'] = None; state['last_type'] = "text"
                state['updated_at'] = time.time()
                add_to_history(t, 'pc', 'text'); emit_state()
        except Exception: pass

    def quick_from_phone(icon, item):
        if state['phone_text']:
            try: pyperclip.copy(state['phone_text'])
            except Exception: pass

    menu = pystray.Menu(
        pystray.MenuItem("Авто: iPhone ➔ ПК",  lambda i, it: toggle("auto_to_pc"),    checked=lambda it: state['auto_to_pc']),
        pystray.MenuItem("Авто: ПК ➔ iPhone",  lambda i, it: toggle("auto_to_phone"), checked=lambda it: state['auto_to_phone']),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Открыть панель",            open_browser),
        pystray.MenuItem("ПК ➔ iPhone вручную",     quick_to_phone),
        pystray.MenuItem("iPhone ➔ буфер ПК вручную", quick_from_phone),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Перезапустить", restart_app),
        pystray.MenuItem("Выход", on_exit),
    )

    icon = pystray.Icon("ClipboardServer", create_tray_image(), menu=menu)
    icon.title = "Clipboard Server запущен"
    icon.run()