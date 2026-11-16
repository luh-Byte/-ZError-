@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"
set "PY="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python --version >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python 3 not found.
  echo Install it from https://www.python.org/downloads/ and check "Add python.exe to PATH",
  echo then run this file again.
  pause
  exit /b 1
)
echo Using: %PY%
echo.
%PY% import_tiku.py --apply
echo.
if errorlevel 1 echo [FAILED] see the message above.
echo Done. Press any key to close.
pause >nul
