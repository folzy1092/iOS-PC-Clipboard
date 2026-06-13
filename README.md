# 📋 Clipboard Server

Синхронизация буфера обмена между Windows-ПК и iPhone по локальной сети.  
Текст и изображения — в обе стороны, в реальном времени через WebSocket.

## Возможности

- **iPhone → ПК**: автоматически копирует текст/изображение в буфер Windows
- **ПК → iPhone**: мониторинг буфера ПК и мгновенная отправка на телефон
- Веб-интерфейс с историей и ручной отправкой
- Значок в трее с быстрым управлением
- Работает только в локальной сети (Wi-Fi)

## Требования

- Windows 10/11
- Python 3.9+
- iPhone с Apple Shortcuts

## Установка

```bash
git clone https://github.com/folzy1092/iOS-PC-Clipboard
cd clipboard-server
pip install -r requirements.txt
```

## Запуск

```bash
# Через bat-файл (без консоли)
run.bat

# Или напрямую
pythonw server.pyw
```

После запуска сервер появится в трее. Веб-интерфейс: [http://localhost:5000](http://localhost:5000)

## Настройка (config.py)

| Параметр | По умолчанию | Описание |
|---|---|---|
| `HOST` | `0.0.0.0` | Адрес сервера |
| `PORT` | `5000` | Порт |
| `DEFAULT_AUTO_TO_PC` | `True` | Автокопирование iPhone → ПК при старте |
| `DEFAULT_AUTO_TO_PHONE` | `True` | Автокопирование ПК → iPhone при старте |

## Структура проекта

```
clipboard-server/
├── server.pyw          # Основной файл (Flask + SocketIO + трей)
├── config.py           # Настройки (пути, порт, дефолты)
├── requirements.txt
├── run.bat             # Быстрый запуск на Windows
└── .gitignore
```

## Использование с iPhone (Apple Shortcuts)

Создай шортkat, который делает POST на `http://<IP_ПК>:5000/update` с телом:
```json
{ "data": "<base64 текст или изображение>" }
```

IP компьютера можно узнать командой `ipconfig` в терминале.

## Лицензия

GNU General Public License v3.0
