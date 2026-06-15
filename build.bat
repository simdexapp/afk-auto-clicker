@echo off
REM Build AFKClicker as a one-folder app (fast startup, no per-launch unpack).
REM Prefer package.ps1 for the full exe + ZIP + installer pipeline.
python make_icon.py
python -m PyInstaller --onedir --windowed --name AFKClicker --icon icon.ico ^
    --add-data "icon.ico;." --add-data "web;web" ^
    --collect-all webview --collect-all clr_loader --copy-metadata pythonnet ^
    --hidden-import pystray._win32 --clean --noconfirm app.py
echo.
echo Done. Your app folder is:  %cd%\dist\AFKClicker\  (run AFKClicker.exe inside)
pause
