@echo off
REM One-command build & package: exe + portable ZIP + installer.
REM Optional version arg, e.g.  package.bat 1.1
set "VER=%~1"
if "%VER%"=="" set "VER=1.0"
powershell -ExecutionPolicy Bypass -File "%~dp0package.ps1" -Version %VER%
pause
