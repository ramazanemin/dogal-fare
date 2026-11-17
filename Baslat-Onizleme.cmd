@echo off
rem dogal-fare: on izleme + yerel test ekran^i (gercek fare hareketi YOK)
cd /d "%~dp0"
python -X utf8 scripts\onizleme.py %*
echo.
pause
