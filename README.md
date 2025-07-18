# Telegram‑бот на OpenAI Responses API 📨🤖  
[![GitHub](https://img.shields.io/badge/GitHub-GPTTG-blue?logo=github)](https://github.com/zergont/GPTTG)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Демонстрационный Telegram‑бот, показывающий:

* **OpenAI Responses API** с `previous_response_id` — нет необходимости хранить всю историю чата  
* **Мультимодальность**: текст • фото + подпись • голос (Whisper) • генерация изображений  
* Учёт токенов и стоимости в **SQLite**  
* **Ролевые клавиатуры** (пользователь / админ)  
* Асинхронность, таймауты, автоматический back‑off  
* Пошаговая генерация изображений с выбором формата (вертикальный/горизонтальный)

---

## Содержание
1. [Предварительные требования](#0-предварительные-требования)
2. [Быстрый старт](#1-быстрый-старт)
3. [Переменные окружения](#переменные-окружения-env)
4. [Структура проекта](#структура-проекта)
5. [Примеры использования](#примеры-использования)
6. [Responses API: особенности](#responses-api-особенности)
7. [Рекомендации по работе с файлами](#рекомендации-по-работе-с-файлами)
8. [Важно о форматах файлов](#важно-о-форматах-файлов)
9. [Лицензия](#лицензия)

---

## 0. Предварительные требования

> Пропустите этот шаг, если `python >= 3.9`, `pip` и `poetry` уже есть в `$PATH`.

### Проверяем Python и pip
python3 --version          # >= 3.9
python3 -m pip --version
### Устанавливаем pip (если отсутствует)
python3 -m ensurepip --upgrade
### Устанавливаем Poetry

<details>
<summary>Через официальный инсталлер (рекомендуется)</summary>
curl -sSL https://install.python-poetry.org | python3 -
exec $SHELL            # перезапустить оболочку, чтобы poetry попал в PATH
poetry --version</details>

<details>
<summary>Через <code>pipx</code> (альтернативно)</summary>
pipx install poetry
poetry --version</details>

---

## 1. Быстрый старт

### 1. Клонируйте репозиторий
git clone https://github.com/zergont/GPTTG.git
cd GPTTG
### 2. Создайте виртуальное окружение и установите зависимости

#### Способ A — Poetry (рекомендуется)
# внутри каталога проекта
poetry install          # Poetry сам создаст .venv
poetry shell            # активировать окружение
#### Способ B — venv + pip
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
### 3. Настройте переменные окружения
cp .env.example .env
nano .env       # или любой редактор
Заполните обязательные ключи (`BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_ID`).

### 4. Запустите бота
python3 -m bot.main
> При первом запуске создаётся база `gpttg.db` и таблицы статистики.

---

## Переменные окружения (.env)

| Переменная | Описание | Пример | По умолчанию |
|------------|----------|--------|--------------|
| `BOT_TOKEN` | Токен вашего Telegram‑бота | `123456:ABC-DEF...` | **обязательно** |
| `OPENAI_API_KEY` | API‑ключ OpenAI | `sk-...` | **обязательно** |
| `ADMIN_ID` | Telegram ID администратора | `12345678` | **обязательно** |
| `SYSTEM_PROMPT` | Системный промпт ассистента | `Ты — полезный ассистент.` | `Ты — полезный ассистент.` |
| `OPENAI_PRICE_PER_1K_TOKENS` | Цена 1000 токенов (USD) | `0.002` | `0.002` |
| `WHISPER_PRICE` | Цена расшифровки 1 мин аудио (USD) | `0.006` | `0.006` |
| `DALLE_PRICE` | Цена генерации изображения (USD) | `0.040` | `0.040` |
| `MAX_FILE_MB` | Максимальный размер файла, МБ | `20` | `20` |
| `DEBUG_MODE` | Включить подробный лог (0/1) | `1` | `0` |

---

## Структура проекта
GPTTG/
├── bot/
│   ├── handlers/
│   │   ├── message_handler.py  # Обработчик с индикацией прогресса
│   │   ├── commands.py         # Обработчики команд бота
│   │   ├── document.py         # Обработка PDF документов
│   │   ├── photo.py            # Обработка изображений
│   │   ├── text.py             # Обработка текстовых сообщений
│   │   └── voice.py            # Обработка голосовых сообщений
│   ├── utils/
│   │   ├── openai_client.py    # Улучшенный клиент с увеличенным таймаутом
│   │   ├── progress.py         # Новый модуль для индикации прогресса
│   │   ├── markdown.py         # Форматирование текста в Markdown
│   │   ├── log.py              # Настройка логирования
│   │   └── db.py               # Работа с базой данных SQLite
│   ├── config.py               # Конфигурация и проверка зависимостей
│   ├── keyboards.py            # Ролевые клавиатуры (пользователь/админ)
│   ├── middlewares.py          # БД‑ и error‑middleware
│   └── main.py                 # Основной файл с подключенными роутерами
├── schema.sql                  # Схема базы SQLite для учета токенов
├── pyproject.toml              # Зависимости Poetry
├── requirements.txt            # Зависимости pip
├── .env.example                # Образец переменных окружения
└── README.md                   # Документация проекта

---

## Примеры использования
Пользователь: [отправляет PDF] «Сделай краткое резюме этого документа»
Бот: Анализ PDF: Документ содержит…

Пользователь: Привет! Как дела?
Бот: Привет! У меня всё отлично, чем могу помочь?

Пользователь: [голосовое] «Расскажи анекдот»
Бот: Вы сказали: «Расскажи анекдот»
     Конечно! Вот забавный анекдот для вас…

Пользователь: /img
Бот: Опишите, что нарисовать…
Пользователь: Кот в космосе
Бот: Выберите формат: вертикальный или горизонтальный
Бот: *генерирует изображение с котом в космосе*

---

## Responses API: особенности

OpenAI Responses API позволяет сохранять контекст диалога без необходимости хранить всю историю сообщений:

Пример запроса к Responses API
```python
response = await client.responses.create(
    model="gpt-4o",
    input=[{"type": "message", "content": "Привет, как дела?", "role": "user"}],
    previous_response_id="resp_abc123",  # ID предыдущего ответа
    store=True  # Сохранять ответ для использования в будущих запросах
)
```
Получение текста ответа
```python
text = response.output[0].content[0].text
```
Сохранение ID ответа для следующего запроса
```python
response_id = response.id
```

### Преимущества использования Responses API:

- Экономия токенов — не нужно отправлять всю историю диалога
- Проще управлять долгими диалогами
- Автоматическое управление контекстом на стороне OpenAI
- Возможность продолжить диалог в любой момент

---

## Рекомендации по работе с файлами

* При загрузке пользовательских файлов используйте `purpose: "user_data"`.  
* Для изображений используйте `purpose: "vision"`.  
* Скачивать можно только файлы с `purpose` из списка  
  `assistants_output`, `batch_output`, `fine-tune-results`.  
* Для коллекций свыше 10 000 файлов лучше использовать **Vector Store**.
* Обратите внимание на актуальные ограничения размера файлов в [документации OpenAI](https://platform.openai.com/docs/api-reference/files).

---

## Важно о форматах файлов

* **Responses API поддерживает только PDF-документы для анализа**
* Для изображений поддерживаются PNG, JPEG и WebP
* Файлы с другими форматами вызовут ошибку API

---

## Лицензия

Проект распространяется под лицензией **MIT** — подробнее в файле [LICENSE](LICENSE).

---

**Репозиторий проекта:** <https://github.com/zergont/GPTTG>

---
# Systemd unit-файл для контроля работы бота (start/stop/status)
# ---

## Добавьте этот файл как gpttg-bot.service в /etc/systemd/system/

# [Unit]
# Description=GPTTG Telegram Bot
# After=network.target
#
# [Service]
# Type=simple
# User=botuser  # замените на своего пользователя
# WorkingDirectory=/path/to/GPTTG
# ExecStart=/usr/bin/python3 -m bot.main
# Restart=always
# RestartSec=5
# StandardOutput=append:/path/to/GPTTG/logs/bot.log
# StandardError=append:/path/to/GPTTG/logs/bot.log
# Environment=PYTHONUNBUFFERED=1
#
# [Install]
# WantedBy=multi-user.target

## Команды для управления:
# sudo systemctl daemon-reload
# sudo systemctl enable gpttg-bot
# sudo systemctl start gpttg-bot
# sudo systemctl stop gpttg-bot
# sudo systemctl status gpttg-bot
#
# После перезагрузки сервера бот стартует автоматически.
