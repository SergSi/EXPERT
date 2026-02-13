@echo off
chcp 65001 >nul
cls

cd /d "D:\YandexDisk\WORK\EXPERT\SYSTEM" || (
    echo ERROR: Cannot change directory
    pause
    exit /b 1
)

if not exist "app.py" (
    echo ERROR: File app.py not found
    pause
    exit /b 1
)

echo Starting Streamlit application...
streamlit run app.py

if errorlevel 1 (
    echo ERROR: Application failed to start
    pause
)