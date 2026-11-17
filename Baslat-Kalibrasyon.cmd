@echo off
rem dogal-fare: kalibrasyon ekrani (insan fare verisi toplama; ESC=bitir+kaydet)
cd /d "%~dp0"
python -X utf8 scripts\kalibrasyon.py %*
echo.
pause
