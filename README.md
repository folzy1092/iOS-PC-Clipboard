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

Я создал готовые команды которые можно добавить по ссылке через iCloud

From PC: https://www.icloud.com/shortcuts/8963ffa442c84585ac33677b9e8582b0

To PC: https://www.icloud.com/shortcuts/4fc06151fea74d95aa7174a320fa3378

Настройка адреса сервера
После импорта команд измените адрес в поле URL (вместо DESKTOP-LVUN2I4.local:5000 пропишите данные вашего хоста).

Варианты настройки:

По локальному имени (Рекомендуется): Используйте имя хоста с суффиксом .local (например, http://ИМЯ_ПК.local:5000/update). Этот адрес статичен и не изменится. Узнать имя своего ПК можно через команду hostname в CMD.

По IP-адресу: Узнать текущий IPv4 можно через команду ipconfig в CMD.

Примечание: Настройка через IP-адрес не рекомендуется, так как при динамическом DHCP после перезагрузки роутера IP-адрес компьютера может измениться, что приведет к ошибкам подключения на iPhone. Использование .local решает эту проблему.

На Windows открой порт 5000 в файрволе от имени администратора:
`netsh advfirewall firewall add rule name="Flask 5000" dir=in action=allow protocol=TCP localport=5000`

## Лицензия

GNU General Public License v3.0
