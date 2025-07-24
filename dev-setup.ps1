# PowerShell скрипт для разработки на Windows
# GPTTG Development Setup for Windows

Write-Host "🔧 GPTTG Development Script (Windows)" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Проверка Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "🐍 Python версия: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python не найден! Установите Python 3.9+ с python.org" -ForegroundColor Red
    exit 1
}

# Проверка Poetry
try {
    $poetryVersion = poetry --version 2>&1
    Write-Host "📦 Poetry найден: $poetryVersion" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Poetry не найден, устанавливаем..." -ForegroundColor Yellow
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
    Write-Host "✅ Poetry установлен" -ForegroundColor Green
    Write-Host "💡 Перезапустите PowerShell для обновления PATH" -ForegroundColor Yellow
}

# Создание виртуального окружения
Write-Host "📦 Настройка окружения..." -ForegroundColor Cyan
if (!(Test-Path ".venv")) {
    Write-Host "🔨 Создаю виртуальное окружение..." -ForegroundColor Yellow
    poetry install
    Write-Host "✅ Виртуальное окружение создано" -ForegroundColor Green
} else {
    Write-Host "🔄 Обновляю зависимости..." -ForegroundColor Yellow
    poetry install
    Write-Host "✅ Зависимости обновлены" -ForegroundColor Green
}

# Проверка .env файла
if (!(Test-Path ".env")) {
    Write-Host "⚠️ Файл .env не найден!" -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Write-Host "📋 Копирую .env.example в .env..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "💡 Отредактируйте .env файл с вашими настройками" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Файл .env.example также не найден!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ Файл .env найден" -ForegroundColor Green
}

# Проверка конфигурации
Write-Host "🧪 Тестирование конфигурации..." -ForegroundColor Cyan
try {
    $configTest = poetry run python -c @"
try:
    from bot.config import settings, VERSION
    print(f'✅ Конфигурация загружена')
    print(f'📋 Версия: {VERSION}')
    print(f'🖥️ Платформа: {settings.platform}')
    print(f'🔧 Режим разработки: {settings.is_development}')
    print(f'🔍 Debug режим: {settings.debug_mode}')
except Exception as e:
    print(f'❌ Ошибка конфигурации: {e}')
    exit(1)
"@
    Write-Host $configTest -ForegroundColor Green
} catch {
    Write-Host "❌ Ошибка тестирования конфигурации" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🚀 Готово к разработке!" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Cyan
Write-Host "Команды для запуска:" -ForegroundColor Cyan
Write-Host "  poetry run python -m bot.main  # Запуск бота" -ForegroundColor White
Write-Host "  poetry shell                   # Активация окружения" -ForegroundColor White
Write-Host "  poetry run python -c `"from bot.config import settings; print('OK')`"  # Тест" -ForegroundColor White
Write-Host ""