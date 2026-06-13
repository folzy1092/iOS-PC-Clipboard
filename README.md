# 📋 Clipboard Server

Синхронизация буфера обмена между Windows-ПК и iPhone по локальной сети.  
Текст и изображения — в обе стороны, в реальном времени через WebSocket.

## Возможности

- **iPhone → ПК**: автоматически копирует текст и изображения в буфер Windows.
- **ПК → iPhone**: мониторинг буфера ПК и мгновенная отправка на телефон.
- Веб-интерфейс с историей и ручной отправкой.
- Значок в трее с быстрым управлением.
- Работает только в локальной сети Wi‑Fi.

## Требования

- Windows 10/11.
- Python 3.9+.
- iPhone с Apple Shortcuts.

## Установка

```bash
git clone https://github.com/folzy1092/iOS-PC-Clipboard
cd iOS-PC-Clipboard
pip install -r requirements.txt
```

## Запуск

```bash
# Через bat-файл (без консоли)
run.bat

# Или напрямую
pythonw server.pyw
```

После запуска сервер появится в трее.  
Веб-интерфейс: [http://localhost:5000](http://localhost:5000)

## Настройка `config.py`

| Параметр | По умолчанию | Описание |
|---|---|---|
| `HOST` | `0.0.0.0` | Адрес сервера |
| `PORT` | `5000` | Порт |
| `DEFAULT_AUTO_TO_PC` | `True` | Автокопирование iPhone → ПК при старте |
| `DEFAULT_AUTO_TO_PHONE` | `True` | Автокопирование ПК → iPhone при старте |

## Структура проекта

```text
clipboard-server/
├── server.pyw          # Основной файл (Flask + SocketIO + трей)
├── config.py           # Настройки (пути, порт, дефолты)
├── requirements.txt
├── run.bat             # Быстрый запуск на Windows
├── .gitignore
└── LICENSE
```

## Использование с iPhone

Я подготовил готовые команды Apple Shortcuts:

- From PC: [iCloud Shortcut](https://www.icloud.com/shortcuts/8963ffa442c84585ac33677b9e8582b0)
- To PC: [iCloud Shortcut](https://www.icloud.com/shortcuts/4fc06151fea74d95aa7174a320fa3378)

### Настройка адреса сервера

После импорта команд измените адрес в поле URL на адрес вашего компьютера.

**Вариант 1 — по имени хоста**  
Используйте имя ПК в локальной сети, например `http://DESKTOP-NAME.local:5000/update`.  
Имя хоста можно узнать через команду:

```bash
hostname
```

**Вариант 2 — по IP-адресу** ([http://192.168.0.1:5000](http://192.168.1.25:5000)) 

Узнать текущий IPv4 можно через:

```bash
ipconfig
```

Если IP меняется после перезапуска роутера, обновите его в Shortcuts.

## Windows Firewall

На Windows открой порт 5000 в файрволе от имени администратора:

```bash
netsh advfirewall firewall add rule name="Flask 5000" dir=in action=allow protocol=TCP localport=5000
```

## Лицензия

Этот проект распространяется под лицензией GNU General Public License v3.0.  
См. файл `LICENSE` для полного текста лицензии.
