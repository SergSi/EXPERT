@echo off
cd /d D:\EXPERT

echo ========================================
echo Launching Expert System
echo ========================================

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Python not found!
        echo Please install Python from python.org
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check and install dependencies
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Create data folder if it doesn't exist
if not exist "data" mkdir data

REM Launch the application
echo.
echo Application is starting...
echo Open in browser: http://localhost:8501
echo.
streamlit run app.py

pause