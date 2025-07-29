# GPTTG — Telegram‑бот на OpenAI Responses API 🤖📮

[![GitHub — GPTTG](https://img.shields.io/badge/GitHub-GPTTG-blue?logo=github)](https://github.com/zergont/GPTTG)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue)](https://github.com/zergont/GPTTG)

<!-- добавьте бейдж CI, если используете GitHub Actions -->

> **GPTTG** — кроссплатформенный Telegram‑бот, показывающий, как использовать **OpenAI Responses API** без хранения всей истории чата. Поддерживает текст, изображения, голос (Whisper) и генерацию картинок.

---

## ✨ Ключевые возможности

* **🔄 Кроссплатформенность:** Windows (разработка) + Linux (продакшен)
* **🚀 Автоматическая установка** с помощью `install.sh` для быстрого развёртывания на Linux
* **Responses API с `previous_response_id`** — экономит токены, не нужен полный лог диалога
* **Мультимодальность:** текст • фото + подпись • голос (Whisper) • `/img` (генерация через DALL‑E)
* Учёт токенов и стоимости в **SQLite**
* **Ролевые клавиатуры** (пользователь / админ)
* **Автообновление по расписанию** через systemd timer
* Асинхронность, автоматический back‑off, увеличенные таймауты
* Пошаговая генерация изображений с выбором вертикального или горизонтального формата

---

## 📚 Содержание

1. [Предварительные требования](#предварительные-требования)
2. [Быстрый старт](#быстрый-старт)
3. [Автоматическая установка на Linux](#автоматическая-установка-на-linux)
4. [Разработка](#разработка)
5. [Переменные окружения](#переменные-окружения)
6. [Структура проекта](#структура-проекта)
7. [Примеры использования](#примеры-использования)
8. [Responses API — особенности](#responses-api-—-особенности)
9. [Работа с файлами](#работа-с-файлами)
10. [Лицензия](#лицензия)

---

## 1 · Предварительные требования

### 🖥️ Windows (разработка)
```powershell
# Установите Python 3.9+ с python.org
python --version      # >= 3.9

# Установите Poetry
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Или через Chocolatey
choco install poetry
```

### 🐧 Linux (продакшен)
```bash
# Проверить версии
python3 --version      # >= 3.9
python3 -m pip --version

# Установить pip (если отсутствует)
python3 -m ensurepip --upgrade

# Установить Poetry
curl -sSL https://install.python-poetry.org | python3 -
exec "$SHELL"           # обновите PATH
poetry --version

# Системные зависимости для автообновления
sudo apt update
sudo apt install -y git

# Git нужен для клонирования и автообновлений
git --version
```

**Системные требования для Linux:**
- Python 3.9+ 
- Poetry (для управления зависимостями)
- Git (для клонирования и автообновлений)
- systemd (для управления сервисами)
- Права sudo (для установки системных сервисов)

> **💡 Рекомендация:** Для продакшн-установки используйте [автоматическую установку](#автоматическая-установка-на-linux) через `install.sh`.

---

## 2 · Быстрый старт

### Шаг 1. Клонируйте репозиторий

```bash
git clone https://github.com/zergont/GPTTG.git
cd GPTTG
```

### Шаг 2. Настройте переменные окружения

**Windows:**
```powershell
Copy-Item .env.example .env
notepad .env   # или любой редактор
```

**Linux:**
```bash
cp .env.example .env
nano .env   # или любой редактор
```

Заполните обязательные поля — `BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_ID`.

### Шаг 3. Создайте окружение и установитеDependencies

<details>
<summary><strong>Способ A — Poetry (рекомендуется)</strong></summary>

**Windows:**
```powershell
poetry install           # создаст .venv и поставитDependencies
poetry run python -m bot.main   # запустить бота вручную
```

**Linux:**
```bash
poetry install           # создаст .venv и поставитDependencies
poetry run python -m bot.main   # запустить бота вручную
```

</details>

<details>
<summary><strong>Способ B — venv + pip</strong></summary>

**Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

python -m bot.main             # запустить бота вручную
```

**Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

python3 -m bot.main             # запустить бота вручную
```

</details>

### Шаг 4. Запустите бота как systemd‑сервис (только Linux)

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

### Шаг 5. Автообновление (только Linux)

В корне проекта есть скрипт **`update_bot.sh`**:

```bash
chmod +x update_bot.sh
sudo ./update_bot.sh
```

Скрипт:
- делает `git pull`
- обновляет зависимости (`poetry install`)
- перезапускает сервис
- показывает статус

**Автообновление по времени:**
Бот автоматически проверяет наличие новой версии на GitHub каждый день в 10:00 UTC (13:00 МСК) с помощью планировщика aiocron. Если доступна новая версия, администратору приходит уведомление с предложением обновиться.

**Ручное обновление:**
Администратор может запустить обновление в любое время командой `/update` в Telegram.

---

## 3 · Автоматическая установка на Linux

### 🚀 Быстрая установка на голый сервер

Для быстрого разбёртывания бота на свежем Linux-сервере используйте скрипт автоматической установки:

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/zergont/GPTTG.git
cd GPTTG

# 2. Настройте .env файл (обязательно!)
cp .env.example .env
nano .env  # заполните BOT_TOKEN, OPENAI_API_KEY, ADMIN_ID

# 3. Установите зависимости
poetry install

# 4. Запустите автоматическую установку
chmod +x bot/deploy/install.sh
sudo bot/deploy/install.sh
```

### 📋 Что делает скрипт установки

Скрипт `bot/deploy/install.sh` автоматически:

- **📦 Копирует systemd-unit файлы:**
  - `gpttg-bot.service` → основная служба бота
  - `gpttg-update.service` → служба автообновления  
  - `gpttg-update.timer` → таймер ежедневного обновления

- **🔧 Настраивает права доступа:**
  - Делает `update_bot.sh` исполняемым
  - Устанавливает корректные разрешения для всех скриптов

- **🔄 Запускает службы:**
  - Перезагружает конфигурацию systemd
  - Включает автозапуск бота при загрузке системы
  - Включает таймер автообновления
  - Запускает бота

- **✅ Показывает статус установки:**
  - Отображает состояние службы бота  
  - Отображает состояние таймера обновлений
  - Подтверждает успешную установку

### 🎯 После установки

После успешной установки у вас будет:

- **🤖 Работающий бот** под управлением systemd
- **⏰ Автообновление** каждый день в случайное время
- **📊 Мониторинг** через systemd и journald
- **🔄 Автозапуск** при перезагрузке сервера

### 🔧 Управление установленным ботом

```bash
# Проверить статус
sudo systemctl status gpttg-bot
sudo systemctl status gpttg-update.timer

# Посмотреть логи
sudo journalctl -u gpttg-bot -f
sudo journalctl -u gpttg-update -f

# Перезапустить бота
sudo systemctl restart gpttg-bot

# Принудительно запустить обновление
sudo systemctl start gpttg-update
```

### ⚠️ Требования для автоматической установки

- **Права root** для установки systemd-сервисов
- **Poetry** уже установлен в системе
- **Git** для клонирования и обновлений
- **Заполненный .env файл** с корректными токенами

> **💡 Совет:** Используйте этот способ для продакшн-серверов. Для разработки лучше использовать ручную установку из раздела "Быстрый старт".

---

## 4 · Разработка

### 🔧 Быстрая настройка среды разработки

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
# Запустите автоматическую настройку
.\dev-setup.ps1

# Или вручную:
poetry install
poetry run python -c "from bot.config import settings; print('✅ Конфигурация OK')"
poetry run python -m bot.main
```

</details>

<details>
<summary><strong>Linux/macOS (Bash)</strong></summary>

```bash
# Запустите автоматическую настройку
chmod +x dev-setup.sh
./dev-setup.sh

# Или вручную:
poetry install
poetry run python -c "from bot.config import settings; print('✅ Конфигурация OK')"
poetry run python -m bot.main
```

</details>

### 🐛 Отладка

Бот автоматически определяет режим разработки и включает отладочные сообщения:

- **Разработка:** Debug включен по умолчанию
- **Продакшен:** Debug выключен по умолчанию

Принудительное включение debug режима:
```bash
# В .env файле
DEBUG_MODE=1
```

### 🧪 Тестирование

```bash
# Проверка конфигурации
poetry run python -c "from bot.config import settings, VERSION; print(f'Версия: {VERSION}, Платформа: {settings.platform}')"

# Проверка подключения к API
poetry run python -c "from bot.utils.openai import OpenAIClient; import asyncio; asyncio.run(OpenAIClient.get_available_models())"
```

---

## 5 · Переменные окружения

| Переменная                   | Описание                           | Пример                     | По умолчанию |
| ---------------------------- | ---------------------------------- | -------------------------- | ------------ |
| **`BOT_TOKEN`**              | Токен вашего Telegram‑бота         | `123456:ABC-DEF...`        | —            |
| **`OPENAI_API_KEY`**         | API‑ключ OpenAI                    | `sk-...`                   | —            |
| **`ADMIN_ID`**               | Telegram ID администратора         | `12345678`                 | —            |
| `SYSTEM_PROMPT`              | Системный промпт ассистента        | `Ты — полезный ассистент.` | то же        |
| `OPENAI_PRICE_PER_1K_TOKENS` | Цена за 1000 токенов (USD)         | `0.002`                    | `0.002`      |
| `WHISPER_PRICE`              | Цена расшифровки 1 мин аудио (USD) | `0.006`                    | `0.006`      |
| `DALLE_PRICE`                | Цена генерации картинки (USD)      | `0.040`                    | `0.040`      |
| `MAX_FILE_MB`                | Максимальный размер файла, МБ      | `20`                       | `20`         |
| `DEBUG_MODE`                 | Подробный лог (`0/1`)              | `1`                        | `auto`       |

> Обязательные переменные отмечены **жирным**.  
> `DEBUG_MODE` автоматически определяется: `1` для разработки, `0` для продакшена.

---

## 6 · Структура проекта

<details>
<summary>Развернуть дерево файлов</summary>

```text
GPTTG/
├── bot/
│   ├── handlers/
│   │   ├── __init__.py          # сборка всех роутеров
│   │   ├── commands.py          # /start, /help, /img, /stat, /models
│   │   ├── admin_update.py      # админская команда /update
│   │   ├── document.py          # PDF‑документы через OpenAI Files API
│   │   ├── photo.py             # изображения с мультимодальным анализом
│   │   ├── text.py              # текстовые сообщения с прогресс-индикатором
│   │   └── voice.py             # голосовые сообщения (Whisper)
│   ├── utils/
│   │   ├── openai/              # 🆕 модульный OpenAI клиент
│   │   │   ├── __init__.py      # основной экспорт OpenAIClient
│   │   │   ├── base.py          # базовые настройки клиента
│   │   │   ├── chat.py          # Responses API для чата
│   │   │   ├── files.py         # управление файлами
│   │   │   ├── models.py        # управление моделями
│   │   │   ├── dalle.py         # генерация изображений
│   │   │   └── whisper.py       # распознавание речи
│   │   ├── __init__.py          # инициализация утилит
│   │   ├── db.py                # работа с SQLite базой данных
│   │   ├── errors.py            # централизованная обработка ошибок
│   │   ├── http_client.py       # HTTP клиент для загрузки файлов
│   │   ├── log.py               # настройка логирования
│   │   ├── html.py              # HTML форматирование для Telegram
│   │   ├── progress.py          # индикаторы прогресса обработки
│   │   └── single_instance.py   # проверка единственного экземпляра
│   ├── deploy/                  # 🚀 автоматическая установка на Linux
│   │   ├── install.sh           # скрипт автоматической установки
│   │   └── systemd/             # systemd unit-файлы
│   │       ├── gpttg-update.service  # служба автообновления
│   │       └── gpttg-update.timer    # таймер ежедневного обновления
│   ├── __init__.py              # экспорт основного router
│   ├── config.py                # конфигурация и переменные окружения
│   ├── keyboards.py             # inline / reply клавиатуры
│   ├── middlewares.py           # middleware для БД и обработки ошибок
│   └── main.py                  # точка входа приложения
├── schema.sql                   # схема SQLite базы данных
├── pyproject.toml               # зависимости Poetry
├── requirements.txt             # зависимости pip (альтернатива)
├── .env.example                 # пример конфигурации
├── .gitignore                   # исключения Git
├── dev-setup.sh                 # настройка разработки (Linux/macOS)
├── dev-setup.ps1                # настройка разработки (Windows)
├── update_bot.sh                # скрипт автообновления (Linux)
├── gpttg-bot.service            # systemd сервис для продакшена
└── README.md                    # этот файл
```
</details>

---

## 7 · Примеры использования

| Действие пользователя             | Ответ бота                                                             |
| --------------------------------- | ---------------------------------------------------------------------- |
| **PDF**: «Сделай краткое резюме…» | *Анализ PDF*: документ содержит…                                       |
| **Текст**: «Привет! Как дела?»    | Привет! У меня всё отлично, чем могу помочь?                           |
| **Голос**: «Расскажи анекдот»     | *Вы сказали*: …<br>Конечно! Вот забавный анекдот…                      |
| `/img` → «Кот в космосе»          | *Выберите формат*: вертикальный/горизонтальный → генерируется картинка |

---

## 8 · Responses API — особенности

OpenAI Responses API позволяет сохранять контекст диалога, передавая в запрос **только** последнее сообщение и идентификатор предыдущего ответа:

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
* не нужно вручную резать диалог;
* можно «подхватить» разговор спустя время.

---

## 9 · Работа с файлами

* Поддерживаются **только PDF** (для анализа) и изображения PNG / JPEG / WebP.
* Максимальный размер управляется `MAX_FILE_MB` (по умолчанию 20 МБ, максимум 100 МБ).
* При загрузке PDF бот делает `purpose="user_data"` и дальше вы можете задавать вопросы к файлу.

---

## 10 · Лицензия

Код распространяется под лицензией **MIT** — подробности в [LICENSE](LICENSE).

---

*Репозиторий открыт для pull‑request'ов! Буду рад вашим идеям и улучшениям.*
