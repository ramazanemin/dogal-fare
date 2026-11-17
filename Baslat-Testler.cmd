@echo off
rem dogal-fare: birim testler (45 adim; gercek girdi gonderilmez)
cd /d "%~dp0"
python -m unittest discover -s tests -v
echo.
pause
