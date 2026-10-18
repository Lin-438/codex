@echo off
setlocal
pushd "%~dp0" || exit /b 1
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install 64-bit Python 3.14, 3.12, or 3.11 from python.org with the launcher.
  goto fail
)
if exist ".venv\Scripts\python.exe" goto install
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>nul
if not errorlevel 1 (
  py -3.12 -m venv .venv
  goto venv_created
)
py -3.11 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>nul
if not errorlevel 1 (
  py -3.11 -m venv .venv
  goto venv_created
)
py -3.14 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>nul
if not errorlevel 1 (
  py -3.14 -m venv .venv
  goto venv_created
)
echo Supported 64-bit Python 3.14, 3.12, or 3.11 not found.
goto fail
:venv_created
if errorlevel 1 goto fail
:install
set "REQ=requirements.txt"
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 14) else 1)" >nul 2>nul
if not errorlevel 1 set "REQ=requirements-py314.txt"
if "%REQ%"=="requirements.txt" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 11), (3, 12)) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo Existing .venv uses an unsupported Python version. Rename that .venv and rerun this script.
    goto fail
  )
)
echo Installing %REQ% into local virtual environment...
".venv\Scripts\python.exe" -m pip install -r "%REQ%"
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto fail
if exist "models\hand_landmarker.task" goto check_model
".venv\Scripts\python.exe" tools.py download-model
if errorlevel 1 (
  echo Model download failed. Download the official file manually; see README.md.
  goto fail
)
:check_model
".venv\Scripts\python.exe" smoke_model.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto fail
echo Setup completed. Run demo-windows.cmd to check your camera.
popd
pause
exit /b 0
:fail
echo Setup stopped. Read the error above and README.md.
popd
pause
exit /b 1
