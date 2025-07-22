# GPTTG — Telegram‑бот на OpenAI Responses API 🤖📮

[![GitHub — GPTTG](https://img.shields.io/badge/GitHub-GPTTG-blue?logo=github)](https://github.com/zergont/GPTTG)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<!-- добавьте бейдж CI, если используете GitHub Actions -->

> **GPTTG** — демонстрационный Telegram‑бот, показывающий, как использовать **OpenAI Responses API** без хранения всей истории чата. Поддерживает текст, изображения, голос (Whisper) и генерацию картинок.

---

## ✨ Ключевые возможности

* **Responses API с `previous_response_id`** — экономит токены, не нужен полный лог диалога
* **Мультимодальность:** текст • фото + подпись • голос (Whisper) • `/img` (генерация через DALL‑E)
* Учёт токенов и стоимости в **SQLite**
* **Ролевые клавиатуры** (пользователь / админ)
* Асинхронность, автоматический back‑off, увеличенные таймауты
* Пошаговая генерация изображений с выбором вертикального или горизонтального формата

---

## 📚 Содержание

1. [Предварительные требования](#предварительные-требования)
2. [Быстрый старт](#быстрый-старт)
3. [Переменные окружения](#переменные-окружения)
4. [Структура проекта](#структура-проекта)
5. [Примеры использования](#примеры-использования)
6. [Responses API — особенности](#responses-api-—-особенности)
7. [Работа с файлами](#работа-с-файлами)
8. [Лицензия](#лицензия)

---

## 1 · Предварительные требования

> Пропустите этот шаг, если **Python ≥ 3.9**, `pip` и `poetry` уже в `$PATH`.

```bash
# проверить версии
python3 --version      # >= 3.9
python3 -m pip --version

# установить pip (если отсутствует)
python3 -m ensurepip --upgrade

# установить Poetry (рекомендуемый менеджер зависимостей)
curl -sSL https://install.python-poetry.org | python3 -
exec "$SHELL"           # обновите PATH
poetry --version
```

---

## 2 · Быстрый старт

### Шаг 1. Клонируйте репозиторий

```bash
git clone https://github.com/zergont/GPTTG.git
cd GPTTG
```

### Шаг 2. Настройте переменные окружения

```bash
cp .env.example .env
nano .env   # или любой редактор
```

Заполните обязательные поля — `BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_ID`.

### Шаг 3. Создайте окружение и установите зависимости

<details>
<summary><strong>Способ A — Poetry (рекомендуется)</strong></summary>

```bash
poetry install           # создаст .venv и поставит зависимости
poetry run python -m bot.main   # запустить бота вручную
```

</details>

<details>
<summary><strong>Способ B — venv + pip</strong></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

python3 -m bot.main             # запустить бота вручную
```

</details>

### Шаг 4. Запустите бота как systemd‑сервис (Production‑режим)

В корне проекта уже есть готовый файл сервиса `gpttg-bot.service`. Его можно скопировать в нужный каталог:

```bash
sudo cp gpttg-bot.service /etc/systemd/system/gpttg-bot.service
```

При необходимости отредактируйте параметры (например, пути, пользователя) под вашу систему.

Затем выполните:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gpttg-bot
```

#### Управление сервисом

```bash
sudo systemctl start gpttg-bot     # запустить (если не запущен)
sudo systemctl restart gpttg-bot   # перезапустить
sudo systemctl stop gpttg-bot      # остановить
sudo systemctl status gpttg-bot    # статус + последние строки лога
sudo journalctl -u gpttg-bot -f    # «хвост» лога в реальном времени
sudo systemctl enable gpttg-bot    # включить автозапуск при загрузке
sudo systemctl disable gpttg-bot   # убрать автозапуск
```

### Шаг 5. Автообновление

В корне проекта есть скрипт **`update_bot.sh`**:

```bash
chmod +x update_bot.sh
sudo ./update_bot.sh
```

Скрипт:
- делает `git pull`
- обновляет зависимости (`poetry install`)
- перезапускает сервис
- показывает статус

**Автообновление по времени:**
Бот автоматически проверяет наличие новой версии на GitHub каждый день в 10:00 UTC (13:00 МСК) с помощью планировщика aiocron. Если доступна новая версия, администратору приходит уведомление с предложением обновиться.

---

## 3 · Переменные окружения

| Переменная                   | Описание                           | Пример                     | По умолчанию |
| ---------------------------- | ---------------------------------- | -------------------------- | ------------ |
| **`BOT_TOKEN`**              | Токен вашего Telegram‑бота         | `123456:ABC-DEF...`        | —            |
| **`OPENAI_API_KEY`**         | API‑ключ OpenAI                    | `sk-...`                   | —            |
| **`ADMIN_ID`**               | Telegram ID администратора         | `12345678`                 | —            |
| `SYSTEM_PROMPT`              | Системный промпт ассистента        | `Ты — полезный ассистент.` | то же        |
| `OPENAI_PRICE_PER_1K_TOKENS` | Цена за 1000 токенов (USD)         | `0.002`                    | `0.002`      |
| `WHISPER_PRICE`              | Цена расшифровки 1 мин аудио (USD) | `0.006`                    | `0.006`      |
| `DALLE_PRICE`                | Цена генерации картинки (USD)      | `0.040`                    | `0.040`      |
| `MAX_FILE_MB`                | Максимальный размер файла, МБ      | `20`                       | `20`         |
| `DEBUG_MODE`                 | Подробный лог (`0/1`)              | `1`                        | `0`          |

> Обязательные переменные отмечены **жирным**.

---

## 4 · Структура проекта

<details>
<summary>Развернуть дерево файлов</summary>

```text
GPTTG/
├── bot/
│   ├── handlers/
│   │   ├── message_handler.py   # индикатор прогресса
│   │   ├── commands.py          # /start, /help, /img, …
│   │   ├── document.py          # PDF‑документы
│   │   ├── photo.py             # изображения
│   │   ├── text.py              # текстовые сообщения
│   │   └── voice.py             # голосовые сообщения (Whisper)
│   ├── utils/
│   │   ├── openai_client.py     # обёртка для OpenAI SDK с таймаутами
│   │   ├── progress.py          # красивый прогресс‑бар
│   │   ├── markdown.py          # форматирование вывода
│   │   └── log.py               # настройка логов
│   ├── db.py                    # SQLite‑ORM
│   ├── config.py                # проверка зависимостей + .env
│   ├── keyboards.py             # inline / reply клавиатуры
│   ├── middlewares.py           # БД‑ и error‑middleware
│   └── main.py                  # точка входа
├── schema.sql                    # схема БД
├── pyproject.toml               # зависимости Poetry
├── requirements.txt             # зависимости pip
├── .env.example                 # пример конфигурации
├── update_bot.sh                # автообновление и рестарт
└── README.md                    # этот файл
```

</details>

---

## 5 · Примеры использования

| Действие пользователя             | Ответ бота                                                             |
| --------------------------------- | ---------------------------------------------------------------------- |
| **PDF**: «Сделай краткое резюме…» | *Анализ PDF*: документ содержит…                                       |
| **Текст**: «Привет! Как дела?»    | Привет! У меня всё отлично, чем могу помочь?                           |
| **Голос**: «Расскажи анекдот»     | *Вы сказали*: …<br>Конечно! Вот забавный анекдот…                      |
| `/img` → «Кот в космосе»          | *Выберите формат*: вертикальный/горизонтальный → генерируется картинка |

---

## 6 · Responses API — особенности

OpenAI Responses API позволяет сохранять контекст диалога, передавая в запрос **только** последнее сообщение и идентификатор предыдущего ответа:

```python
response = await client.responses.create(
    model="gpt-4o",
    input=[{"type": "message", "content": "Привет, как дела?", "role": "user"}],
    previous_response_id="resp_abc123",  # ID предыдущего ответа
    store=True                            # сохранять ответ для будущего контекста
)
print(response.output[0].content[0].text)
```

Преимущества:

* экономия токенов;
* не нужно вручную резать диалог;
* можно «подхватить» разговор спустя время.

---

## 7 · Работа с файлами

* Поддерживаются **только PDF** (для анализа) и изображения PNG / JPEG / WebP.
* Максимальный размер управляется `MAX_FILE_MB` (по умолчанию 20 МБ, максимум 100 МБ).
* При загрузке PDF бот делает `purpose="user_data"` и дальше вы можете задавать вопросы к файлу.

---

## 8 · Лицензия

Код распространяется под лицензией **MIT** — подробности в [LICENSE](LICENSE).

---

*Репозиторий открыт для pull‑request’ов! Буду рад вашим идеям и улучшениям.*
