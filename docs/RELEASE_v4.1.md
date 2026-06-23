A fast, modern **auto-clicker + key-presser + macro tool for Windows** that works inside most games. Native desktop app, clean dark UI.

## Download
- **`AFKClicker-Setup-v4.1.exe`** — installer (Start Menu, optional desktop shortcut, clean uninstaller). Per-user, no admin.
- **`AFKClicker-v4.1-win64.zip`** — portable. Unzip and run `AFKClicker.exe`.

Windows 10/11 (64-bit). Uses the built-in WebView2 runtime.

> ⚠️ **This build is not code-signed yet**, so Windows SmartScreen will show *"Windows protected your PC."* Click **More info → Run anyway**. (A code-signed build is coming — it'll remove this prompt.) Verify your download with the checksums below if you like.

## Features
- **Auto Click** — repeat a mouse click or key press at a precise interval (ms/sec/min) with optional jitter.
- **Macro** — build or **record** a sequence of clicks/keys/waits and loop it.
- **Anti-AFK** — wiggle the mouse or tap a key every N seconds.
- **Pixel trigger** — only click when a screen pixel matches a color.
- **Per-game profiles**, global hotkeys (F6 start/stop, F8 panic, F4 capture, F9 stop recording), system tray, single-instance lock, and one-click in-app uninstall.

## Why it works in games
Mouse via Win32 `SendInput`, keys via hardware scan codes (DirectInput-compatible), hotkeys via physical key state. *Note: kernel-level anti-cheat may still block synthetic input — intended for AFK/idle/single-player.*

## SHA-256 checksums
```
AFKClicker-Setup-v4.1.exe   D38360A41D6A8483B0D0ADFF2D612D8085EA780A042F8AA873D2E163D16372C0
AFKClicker-v4.1-win64.zip   ED20C27DF93374E00BF1506592EA4788B0FD63DCD8B63263F1F7EC4FC74985F4
```

## ⚖️ Disclaimer
This tool automates input. Many online games prohibit automation in their Terms of Service and using it there can get your account banned. It's for AFK/idle/single-player use, provided "as is" with no warranty. You're responsible for how you use it.
