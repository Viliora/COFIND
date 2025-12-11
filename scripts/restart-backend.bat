@echo off
echo ========================================
echo   COFIND - Restart Backend Server
echo ========================================
echo.

echo [1/3] Stopping existing Flask server...
echo.

REM Kill process on port 5000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000') do (
    echo Found process: %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo [2/3] Waiting 2 seconds...
timeout /t 2 /nobreak >nul

echo.
echo [3/3] Starting new Flask server...
echo.
echo ========================================
echo   Backend is starting...
echo   URL: http://localhost:5000
echo   Press Ctrl+C to stop
echo ========================================
echo.

cd ..
python app.py

