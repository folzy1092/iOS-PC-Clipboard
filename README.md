# Clipboard

Синхронизация буфера обмена между Windows и iPhone по локальной сети.  
Текст и изображения — в обе стороны, в реальном времени через WebSocket.

---

## Возможности

- **iPhone → ПК** — автоматически кладёт текст или изображение в буфер Windows
- **ПК → iPhone** — мониторит буфер ПК и отдаёт его по запросу с шортката
- Веб-панель с историей, ручной отправкой и переключателями
- Значок в трее с автозагрузкой, быстрыми действиями и перезапуском
- Работает только в локальной сети (Wi-Fi)

---

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
# Без окна консоли (рекомендуется)
run.bat

# Или напрямую
pythonw server.pyw
```

После запуска сервер появится в трее. Веб-панель: [http://localhost:5000](http://localhost:5000)

---

## Структура проекта

```
iOS-PC-Clipboard/
├── server.pyw       # Flask + SocketIO + трей
├── index.html       # Веб-панель
├── config.py        # Настройки (порт, пути, дефолты)
├── requirements.txt
├── run.bat
└── .gitignore
```

## Настройка (config.py)

| Параметр | По умолчанию | Описание |
|---|---|---|
| `HOST` | `0.0.0.0` | Адрес сервера |
| `PORT` | `5000` | Порт |
| `DEFAULT_AUTO_TO_PC` | `True` | Автокопирование iPhone → ПК при старте |
| `DEFAULT_AUTO_TO_PHONE` | `True` | Автокопирование ПК → iPhone при старте |

---

## Apple Shortcuts

Нужны два шортката.

### Шорткат 1 — Отправить с iPhone на ПК

Делает POST на `/update` с base64-контентом из буфера обмена.

```
Действие: URL → http://<IP_ПК>:5000/update
Тело:     {"data": "<base64 содержимое буфера>"}
Метод:    POST
```

Готовый вариант: [To PC (iCloud)](https://www.icloud.com/shortcuts/f6e1fd9a83f848ab9469bdfe9e5295b9)

### Шорткат 2 — Получить с ПК на iPhone 

Делает GET на `/get-phone` и кладёт ответ в буфер iPhone.

```
Действие: URL → http://<IP_ПК>:5000/get-phone
Метод:    GET
Ответ:    {"type": "text", "data": "..."}
         {"type": "image", "data": "<base64>"}
```

IP компьютера: `ipconfig` в терминале, строка **IPv4**.

Готовый вариант: [From PC (iCloud](https://www.icloud.com/shortcuts/8963ffa442c84585ac33677b9e8582b0)

---

## Автозагрузка

Правой кнопкой по иконке в трее → **Автозагрузка с Windows**.  
Записывает `pythonw server.pyw` в реестр `HKCU\...\Run`.  
Галочка рядом с пунктом показывает текущее состояние.

---

## Лицензия

GNU General Public License v3.0
