@echo off
setlocal
title Terra Studio - release build
cd /d "%~dp0"
set "APPVER="
for /f "tokens=2 delims='" %%v in ('findstr /b /c:"APP_VERSION = " terrain.py') do set "APPVER=%%v"
if not defined APPVER set "APPVER=dev"
echo Building Terra Studio %APPVER%
echo.
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY (python -c "import sys" >nul 2>nul && set "PY=python")
if not defined PY goto nopython
if not exist ".buildenv\Scripts\python.exe" (
  echo Making the build environment ...
  %PY% -m venv .buildenv
  if errorlevel 1 goto fail
)
set "BPY=%CD%\.buildenv\Scripts\python.exe"
"%BPY%" -m pip install --upgrade pip
"%BPY%" -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 goto fail
if exist "build" rmdir /s /q "build"
"%BPY%" -m PyInstaller --noconfirm --clean --name TerraStudio --icon "%CD%\icon.ico" --add-data "%CD%\icon.ico;." --hidden-import PIL._tkinter_finder --distpath "%CD%\build\dist" --workpath "%CD%\build\work" --specpath "%CD%\build" "%CD%\terrain_ui.py"
if errorlevel 1 goto fail
set "APPDIR=%CD%\build\dist\TerraStudio"
xcopy /e /i /y "presets" "%APPDIR%\presets" >nul
copy /y "README.md" "%APPDIR%\README.md" >nul
copy /y "CHANGELOG.md" "%APPDIR%\CHANGELOG.md" >nul
xcopy /e /i /y "docs" "%APPDIR%\docs" >nul
if exist "LICENSE" copy /y "LICENSE" "%APPDIR%\LICENSE" >nul
echo Testing the build ...
"%APPDIR%\TerraStudio.exe" make Terran --res 512 > "%CD%\build\selftest.log" 2>&1
if errorlevel 1 (
  type "%CD%\build\selftest.log"
  goto fail
)
if exist "%APPDIR%\out" rmdir /s /q "%APPDIR%\out"
if not exist "release" mkdir "release"
set "ZIPBASE=%CD%\release\TerraStudio-%APPVER%-windows-x64"
set "ZIP=%ZIPBASE%.zip"
if exist "%ZIP%" del "%ZIP%"
"%BPY%" -c "import shutil, sys; shutil.make_archive(sys.argv[1], 'zip', sys.argv[2], 'TerraStudio')" "%ZIPBASE%" "%CD%\build\dist"
if errorlevel 1 goto fail
echo.
echo Done:
echo %ZIP%
echo.
pause
exit /b 0
:nopython
echo.
echo Python 3 was not found on this PC.
echo Install it from https://www.python.org/downloads/ and start this file again.
echo.
pause
exit /b 1
:fail
echo.
echo The build failed - see the messages above.
echo.
pause
exit /b 1
