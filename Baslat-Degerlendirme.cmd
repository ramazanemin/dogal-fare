@echo off
rem dogal-fare: yerel karsilastirma raporu (headless; gercek fare hareketi YOK)
cd /d "%~dp0"
python -X utf8 scripts\degerlendirme.py %*
echo.
pause
