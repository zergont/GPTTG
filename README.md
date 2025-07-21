# Telegram‑бот на OpenAI Responses API 📬🤖

[![GitHub](https://img.shields.io/badge/GitHub-GPTTG-blue?logo=github)](https://github.com/zergont/GPTTG)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<!-- вы можете добавить сюда ещё бейджи, например CI status -->

> **GPTTG** — пример Telegram‑бота с поддержкой **OpenAI Responses API** и мультимодальных запросов.

### Главные возможности

* **Responses API `previous_response_id`** — сохраняет контекст без хранения полной истории.
* **Мультимодальность**: текст, изображения, голос (Whisper) и генерация картинок (DALL·E 3).
* Учёт токенов и стоимости в SQLite.
* Асинхронность, увеличенные таймауты и автоматический back‑off при ошибках.
* Ролевые клавиатуры (user / admin).
* Пошаговая генерация изображений с выбором формата (vertical / horizontal).

---

## Содержание

1. [Предварительные требования](#предварительные-требования)
2. [Быстрый старт](#быстрый-старт)
3. [.env — переменные окружения](#env-переменные-окружения)
4. [Структура проекта](#структура-проекта)
5. [Примеры использования](#примеры-использования)
6. [Особенности Responses API](#особенности-responses-api)
7. [Рекомендации по работе с файлами](#рекомендации-по-работе-с-файлами)
8. [Важно о форматах](#важно-о-форматах)
9. [Лицензия](#лицензия)

---

## Предварительные требования

> Пропустите этот шаг, если **Python ≥ 3.9**, `pip` и `poetry` уже есть в `$PATH`.

```bash
# проверить версии
python3 --version      # >= 3.9
python3 -m pip --version
```

### Установка Poetry

<details>
<summary>Через официальный инсталлер (рекомендуется)</summary>

```bash
curl -sSL https://install.python-poetry.org | python3 -
exec "$SHELL"     # перезапустить shell, чтобы poetry попал в PATH
poetry --version
```

</details>

<details>
<summary>Через <code>pipx</code> (альтернативный вариант)</summary>

```bash
pipx install poetry
poetry --version
```

</details>

---

## Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/zergont/GPTTG.git
cd GPTTG
```

### 2. Установите зависимости

<details>
<summary>Способ A — <strong>Poetry</strong> (рекомендуется)</summary>

```bash
poetry install           # создаст виртуальное окружение .venv
poetry run python -m bot.main   # пробный запуск
```

</details>

<details>
<summary>Способ B — <code>venv</code> + <code>pip</code></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python -m bot.main
```

</details>

### 3. Настройте переменные окружения

```bash
cp .env.example .env
$EDITOR .env     # заполните обязательные ключи BOT_TOKEN / OPENAI_API_KEY / ADMIN_ID
```

### 4. Запуск как systemd‑сервис (опционально)

Создайте файл `/etc/systemd/system/gpttg-bot.service`:

```ini
[Unit]
Description=GPTTG Telegram Bot
After=network.target

[Service]
Type=simple
User=<your‑user>
WorkingDirectory=/opt/GPTTG
ExecStart=/opt/GPTTG/.venv/bin/python -m bot.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable gpttg-bot
sudo systemctl start gpttg-bot
```

Скрипт `update_bot.sh` поможет обновить код и перезапустить сервис:

```bash
chmod +x update_bot.sh
./update_bot.sh
```

---

## .env — переменные окружения

| Переменная                   | Назначение                      | По умолчанию               |
| ---------------------------- | ------------------------------- | -------------------------- |
| `BOT_TOKEN`                  | Токен вашего Telegram‑бота      | — (обязательна)            |
| `OPENAI_API_KEY`             | API‑ключ OpenAI                 | — (обязательна)            |
| `ADMIN_ID`                   | Telegram ID администратора      | — (обязательна)            |
| `SYSTEM_PROMPT`              | Системный промпт                | `Ты — полезный ассистент.` |
| `OPENAI_PRICE_PER_1K_TOKENS` | Цена 1000 токенов, USD          | `0.002`                    |
| `WHISPER_PRICE`              | Цена 1 мин расшифровки, USD     | `0.006`                    |
| `DALLE_PRICE`                | Цена генерации изображения, USD | `0.040`                    |
| `MAX_FILE_MB`                | Макс. размер файла, МБ          | `20`                       |
| `DEBUG_MODE`                 | Подробный лог `0/1`             | `0`                        |

---

## Структура проекта

```text
GPTTG
│
├── bot
│   ├── handlers
│   │   ├── commands.py       # /start, /help и другие команды
│   │   ├── document.py       # обработка PDF‑документов
│   │   ├── message_handler.py# обёртка с индикацией прогресса
│   │   ├── photo.py          # изображения с подписью
│   │   ├── text.py           # обычные текстовые сообщения
│   │   └── voice.py          # голосовые сообщения (Whisper)
│   │
│   ├── utils
│   │   ├── db.py             # SQLite + учёт токенов
│   │   ├── log.py            # настройка логирования
│   │   ├── markdown.py       # форматирование Markdown/HTML
│   │   ├── openai_client.py  # клиент OpenAI с таймаутами
│   │   └── progress.py       # утилита прогресс‑баров
│   │
│   ├── config.py             # настройка и проверка зависимостей
│   ├── keyboards.py          # ролевые клавиатуры
│   ├── middlewares.py        # error‑ и DB‑middleware
│   └── main.py               # точка входа + роутеры
│
├── schema.sql                # схема БД
├── pyproject.toml            # зависимости Poetry
├── requirements.txt          # зависимости pip
├── .env.example              # образец настроек
├── update_bot.sh             # автообновление и рестарт
└── README.md                 # вы читаете это 📝
```

---

## Примеры использования

<details>
<summary>Сделать краткое резюме PDF‑файла</summary>

**Пользователь**: *\[отправляет PDF]* «Сделай краткое резюме этого документа»
**Бот**: Анализ PDF… «Документ содержит…»

</details>

<details>
<summary>Обычный чат</summary>

**Пользователь**: Привет! Как дела?
**Бот**: Привет! У меня всё отлично — чем могу помочь?

</details>

<details>
<summary>Голосовое сообщение</summary>

**Пользователь**: *\[голосовое]* «Расскажи анекдот»
**Бот**: Вы сказали: «Расскажи анекдот». Конечно! Вот забавный анекдот…

</details>

<details>
<summary>Генерация изображения</summary>

**Пользователь**: `/img`
**Бот**: Опишите, что нарисовать…
**Пользователь**: Кот в космосе
**Бот**: Выберите формат: вертикальный или горизонтальный
*(генерирует изображение)*

</details>

---

## Особенности Responses API

```python
response = await client.responses.create(
    model="gpt-4o",
    input=[{"type": "message", "content": "Привет, как дела?", "role": "user"}],
    previous_response_id="resp_abc123",  # ID предыдущего ответа
    store=True                             # сохраняем ответ для будущих запросов
)

text = response.output[0].content[0].text
response_id = response.id
```

Преимущества:

* Экономия токенов: не отправляем всю историю каждый раз
* Управление длинными диалогами становится проще
* Контекстом управляет OpenAI — меньше кода на клиенте

---

## Рекомендации по работе с файлами

* Поддерживается **только PDF** для анализа документов.
* Максимальный размер регулируется `MAX_FILE_MB` (по умолчанию 20 МБ, максимум 100 МБ).
* Изображения: PNG, JPEG, WebP.
* Для других типов (Word, Excel…) конвертируйте файл в PDF.

---

## Важно о форматах

> Responses API ▸ анализ документов ➜ **только PDF**.

| Формат                 | Поддержка                   |
| ---------------------- | --------------------------- |
| PDF                    | ✅ анализ текста             |
| PNG / JPEG / WebP      | ✅ отправка в чат, генерация |
| Другие (DOCX, XLSX, …) | ❌ не поддерживается         |

---

## Лицензия

Проект распространяется под лицензией **MIT** — детали в файле [LICENSE](LICENSE).

---

**Репозиторий**: [https://github.com/zergont/GPTTG](https://github.com/zergont/GPTTG)

<!--
🇬🇧 An English README is coming soon — contributions are welcome!
-->
