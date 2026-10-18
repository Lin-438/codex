@echo off
setlocal
pushd "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo First run install-windows.cmd.
  goto done
)
".venv\Scripts\python.exe" app.py %*
:done
popd
pause
