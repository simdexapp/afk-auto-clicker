# =====================================================================
#  AFK Auto Clicker - one-command build & package
#  Produces, in C:\autoclicker\release\ :
#     * AFKClicker.exe                  (raw build, under dist\)
#     * AFKClicker-v<ver>-win64.zip     (portable app)
#     * AFKClicker-Setup-v<ver>.exe     (installer)
#
#  Usage:   powershell -ExecutionPolicy Bypass -File package.ps1
#           powershell -ExecutionPolicy Bypass -File package.ps1 -Version 1.1
# =====================================================================
param([string]$Version = "1.0")

$ErrorActionPreference = "Stop"
$root  = $PSScriptRoot
$dist  = Join-Path $root "dist"
$rel   = Join-Path $root "release"
$stage = Join-Path $rel  "AFKClicker"
$inst  = Join-Path $rel  "installer"
Set-Location $root

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# 0) Make sure nothing is holding the old files (wait for the handle to release).
Get-Process AFKClicker -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 800
if (Test-Path "$dist\AFKClicker") { Remove-Item "$dist\AFKClicker" -Recurse -Force }

# 1) Icon
Step "Generating icon"
python make_icon.py

# 2) Build (ONE-FOLDER for fast startup -- no per-launch unpack)
Step "Building AFKClicker (PyInstaller, onedir)"
python -m PyInstaller --onedir --windowed --name AFKClicker --icon icon.ico `
    --add-data "icon.ico;." --add-data "web;web" `
    --collect-all webview --collect-all clr_loader --copy-metadata pythonnet `
    --hidden-import pystray._win32 --clean --noconfirm app.py
if (-not (Test-Path "$dist\AFKClicker\AFKClicker.exe")) { throw "PyInstaller did not produce the exe" }

# 3) Stage portable files (README/LICENSE/shortcut maker already live in stage)
Step "Staging portable files"
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Remove-Item "$stage\AFKClicker.exe","$stage\_internal" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$dist\AFKClicker\*" $stage -Recurse -Force

# 4) Portable ZIP
Step "Creating portable ZIP"
$zip = Join-Path $rel "AFKClicker-v$Version-win64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$stage\*" -DestinationPath $zip -CompressionLevel Optimal

# 5) Installer (skip gracefully if Inno Setup isn't installed)
Step "Building installer"
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" }
$setupExe = Join-Path $inst "AFKClicker-Setup-v$Version.exe"
if (Test-Path $iscc) {
    New-Item -ItemType Directory -Force -Path $inst | Out-Null
    & $iscc "/DMyAppVersion=$Version" "installer.iss" | Out-Null
} else {
    Write-Host "Inno Setup not found - skipping installer. (winget install JRSoftware.InnoSetup)" -ForegroundColor Yellow
}

# 6) Summary
Step "Done"
function ShowFile($p) {
    if (Test-Path $p) {
        $mb = [math]::Round((Get-Item $p).Length / 1MB, 1)
        Write-Host ("  {0,-40} {1} MB" -f (Split-Path $p -Leaf), $mb) -ForegroundColor Green
    }
}
ShowFile $zip
ShowFile $setupExe
Write-Host "`nOutput folder: $rel"
