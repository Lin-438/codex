@echo off
setlocal
pushd "%~dp0" || exit /b 1
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install 64-bit Python 3.14, 3.12, or 3.11 from python.org with the launcher.
  goto fail
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 14), (3, 12), (3, 11)) else 1)" >nul 2>nul
  if not errorlevel 1 goto install
)
if exist ".venv" call :backup_venv
if errorlevel 1 goto fail
call :make_venv 3.14
if not errorlevel 1 goto install
call :make_venv 3.12
if not errorlevel 1 goto install
call :make_venv 3.11
if not errorlevel 1 goto install
echo Could not create a supported 64-bit Python environment.
goto fail
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

:make_venv
py -%1 -m venv .venv >nul 2>nul
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if str(sys.version_info.major)+'.'+str(sys.version_info.minor)=='%1' and __import__('struct').calcsize('P')==8 else 1)" >nul 2>nul
  if not errorlevel 1 exit /b 0
)
if exist ".venv" call :backup_venv
exit /b 1

:backup_venv
set "BACKUP=.venv-backup-%RANDOM%"
if exist "%BACKUP%" exit /b 1
ren ".venv" "%BACKUP%"
if errorlevel 1 exit /b 1
echo Preserved old virtual environment as %BACKUP%.
exit /b 0
