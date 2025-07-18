# Telegram‑бот на OpenAI Responses API 📨🤖  
[![GitHub](https://img.shields.io/badge/GitHub-GPTTG-blue?logo=github)](https://github.com/zergont/GPTTG)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Демонстрационный Telegram‑бот, показывающий:

* **OpenAI Responses API** с `previous_response_id` — нет необходимости хранить всю историю чата  
* **Мультимодальность**: текст • фото + подпись • голос (Whisper) • генерация изображений  
* Учёт токенов и стоимости в **SQLite**  
* **Ролевые клавиатуры** (пользователь / админ)  
* Асинхронность, таймауты, автоматический back‑off  

---

## Содержание
1. [Предварительные требования](#0-предварительные-требования)
2. [Быстрый старт](#1-быстрый-старт)
3. [Переменные окружения](#переменные-окружения-env)
4. [Структура проекта](#структура-проекта)
5. [Примеры использования](#примеры-использования)
6. [Рекомендации по работе с файлами](#рекомендации-по-работе-с-файлами)
7. [Лицензия](#лицензия)

---

## 0. Предварительные требования

> Пропустите этот шаг, если `python >= 3.9`, `pip` и `poetry` уже есть в `$PATH`.

### Проверяем Python и pip

```bash
python --version          # >= 3.9
python -m pip --version
```

### Устанавливаем pip (если отсутствует)

```bash
python -m ensurepip --upgrade
```

### Устанавливаем Poetry

<details>
<summary>Через официальный инсталлер (рекомендуется)</summary>

```bash
curl -sSL https://install.python-poetry.org | python3 -
exec $SHELL            # перезапустить оболочку, чтобы poetry попал в PATH
poetry --version
```
</details>

<details>
<summary>Через <code>pipx</code> (альтернативно)</summary>

```bash
pipx install poetry
poetry --version
```
</details>

---

## 1. Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/zergont/GPTTG.git
cd GPTTG
```

### 2. Создайте виртуальное окружение и установите зависимости

#### Способ A — Poetry (рекомендуется)

```bash
# внутри каталога проекта
poetry install          # Poetry сам создаст .venv
poetry shell            # активировать окружение
```

#### Способ B — venv + pip

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Настройте переменные окружения

```bash
cp .env.example .env
nano .env       # или любой редактор
```

Заполните обязательные ключи (`BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_ID`).

### 4. Запустите бота

```bash
python -m bot.main
```

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

---

## Структура проекта

```text
GPTTG/
├── bot/
│   ├── handlers/      # обработчики сообщений
│   ├── utils/         # утилиты: OpenAI, БД, логирование
│   ├── config.py      # конфигурация и проверка зависимостей
│   ├── keyboards.py   # ролевые клавиатуры
│   ├── middlewares.py # БД‑ и error‑middleware
│   └── main.py        # точка входа приложения
├── schema.sql         # схема базы SQLite
├── pyproject.toml     # зависимости Poetry
├── requirements.txt   # зависимости pip
├── .env.example       # образец переменных окружения
└── README.md          # документация проекта
```

---

## Примеры использования

```text
Пользователь: [отправляет PDF] «Сделай краткое резюме этого документа»
Бот: Анализ PDF: Документ содержит…

Пользователь: [отправляет CSV] «Найди аномалии в данных»
Бот: Анализ CSV: Обнаружены следующие аномалии…

Пользователь: Привет! Как дела?
Бот: Привет! У меня всё отлично, чем могу помочь?

Пользователь: [голосовое] «Расскажи анекдот»
Бот: Вы сказали: «Расскажи анекдот»
     Конечно! Вот забавный анекдот для вас…

Пользователь: /img космический кот в скафандре
Бот: *генерирует изображение с космическим котом*
```

---

## Рекомендации по работе с файлами

* При загрузке пользовательских файлов используйте `purpose: "user_data"`.  
* Для изображений используйте `purpose: "vision"`.  
* Скачивать можно только файлы с `purpose` из списка  
  `assistants_output`, `batch_output`, `fine-tune-results`.  
* Для коллекций свыше 10 000 файлов лучше использовать **Vector Store**.

---

## Лицензия

Проект распространяется под лицензией **MIT** — подробнее в файле [LICENSE](LICENSE).

---

**Репозиторий проекта:** <https://github.com/zergont/GPTTG>
