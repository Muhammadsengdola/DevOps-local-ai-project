@echo off
setlocal
pushd "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_and_run.ps1"
if errorlevel 1 (
    echo.
    echo Setup failed. Read the error above, then press any key to close.
    pause >nul
    popd
    exit /b 1
)

echo.
echo Setup finished. Press any key to close.
pause >nul
popd
