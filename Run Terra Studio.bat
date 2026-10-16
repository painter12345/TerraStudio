@echo off
title Terra Studio
cd /d "%~dp0"
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY (python -c "import sys" >nul 2>nul && set "PY=python")
if not defined PY goto nopython
%PY% -c "import numpy, PIL, tkinter; assert tuple(int(x) for x in PIL.__version__.split('.')[:2]) >= (11, 2)" >nul 2>nul
if errorlevel 1 (
  echo Installing numpy and Pillow, this only happens once ...
  %PY% -m pip install --user --upgrade -r requirements.txt
)
%PY% -c "import numpy, PIL, tkinter" >nul 2>nul
if errorlevel 1 goto nolibs
echo Terra Studio is running. Keep this window open while you use it.
%PY% terrain_ui.py
if errorlevel 1 pause
exit /b 0
:nopython
echo.
echo Python 3 was not found on this PC.
echo Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then start this file again.
echo.
pause
exit /b 1
:nolibs
echo.
echo numpy or Pillow could not be installed automatically.
echo Open a command prompt and run:  %PY% -m pip install -r requirements.txt
echo.
pause
exit /b 1
