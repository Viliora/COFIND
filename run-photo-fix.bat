@echo off
REM Script untuk menjalankan diagnostic dan fix photo URL errors
REM Usage: run-photo-fix.bat

cd /d "%~dp0"

echo.
echo ========================================
echo COFIND - Photo URL Diagnostic & Fix
echo ========================================
echo.
echo Project ID: cpnzglvpqyugtacodwtr
echo Correct Format: https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp
echo.

echo Pastikan:
echo 1. App sudah berjalan di http://localhost:5174
echo 2. Sudah login dengan account yang punya akses Supabase
echo 3. Browser DevTools Console siap
echo.

echo Instruksi:
echo 1. Buka app di browser: http://localhost:5174
echo 2. Buka DevTools (F12) - pilih tab "Console"
echo 3. Copy-paste salah satu command berikut:
echo.
echo   OPTION A (Recommended - dengan diagnostic):
echo   await window.diagnosticPhotoUrl.diagnosePhotoUrls();
echo   await window.fixPhotoUrl.fixAllPhotoUrls();
echo.
echo   OPTION B (Faster - bulk fix):
echo   await window.fixPhotoUrl.fixAllPhotoUrlsBulk();
echo.
echo 4. Tunggu proses selesai
echo 5. Refresh browser (Ctrl + F5)
echo.

pause
