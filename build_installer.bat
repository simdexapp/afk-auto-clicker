@echo off
REM Compiles the Setup installer from installer.iss.
REM Requires Inno Setup (install once:  winget install JRSoftware.InnoSetup)
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
"%ISCC%" installer.iss
echo.
echo Done. Installer is in:  %cd%\release\installer\
pause
