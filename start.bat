@echo off
cd /d D:\YandexDisk\WORK\EXPERT

echo ========================================
echo Запуск экспертной системы
echo ========================================

REM Проверяем наличие виртуального окружения
if not exist "venv\Scripts\activate.bat" (
    echo Создаём виртуальное окружение...
    python -m venv venv
    if errorlevel 1 (
        echo ОШИБКА: Python не найден!
        echo Установите Python с python.org
        pause
        exit /b 1
    )
)

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

REM Проверяем и устанавливаем зависимости
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Устанавливаем зависимости...
    pip install -r requirements.txt
)

REM Создаём папку data, если её нет
if not exist "data" mkdir data

REM Запускаем приложение
echo.
echo Приложение запускается...
echo Откройте в браузере: http://localhost:8501
echo.
streamlit run app.py

pause