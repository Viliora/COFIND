@echo off
REM Start web-based database viewer
echo =========================================
echo Starting Web-based Database Viewer
echo =========================================
echo.
echo Opening browser...
start http://localhost:5001
echo.
echo Starting server...
python start_db_viewer.py
