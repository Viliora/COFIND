@echo off
REM Script untuk membuka localhost di browser
REM Usage: open-localhost.bat [frontend|backend|both]

set TARGET=%1
if "%TARGET%"=="" set TARGET=both

set FRONTEND_URL=http://localhost:5173
set BACKEND_URL=http://localhost:5000

echo ========================================
echo   COFIND - Buka Localhost
echo ========================================
echo.

if "%TARGET%"=="frontend" (
    echo Membuka Frontend: %FRONTEND_URL%
    start %FRONTEND_URL%
) else if "%TARGET%"=="backend" (
    echo Membuka Backend: %BACKEND_URL%
    start %BACKEND_URL%
) else if "%TARGET%"=="both" (
    echo Membuka Frontend: %FRONTEND_URL%
    start %FRONTEND_URL%
    timeout /t 1 /nobreak >nul
    echo Membuka Backend: %BACKEND_URL%
    start %BACKEND_URL%
) else (
    echo Usage: open-localhost.bat [frontend^|backend^|both]
    echo Default: both
)

echo.
echo Selesai!
pause

