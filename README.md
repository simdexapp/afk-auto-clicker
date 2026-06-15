# 🖱️ AFK Auto Clicker

A fast, modern **auto-clicker + key-presser + macro tool for Windows** that works inside most games. Built for AFK farming, idle games, and single-player automation — with a clean, native desktop UI.

> ⚠️ **Use responsibly.** Many online games forbid input automation in their Terms of Service and using this in them can get your account banned. It's meant for AFK / idle / single-player use. See [Disclaimer](#-disclaimer).

---

## ✨ Features

- **Auto Click** — repeat a mouse click *or* a key press at a precise interval (ms / sec / min), with optional randomized jitter for human-like timing.
- **Macro** — build a sequence of clicks, key presses, and waits, then loop it. **Record** your real actions and replay them.
- **Anti-AFK** — every N seconds, nudge the mouse or tap a key so you don't get flagged idle.
- **Pixel trigger** — only click when a chosen screen pixel matches a color (e.g. only when a button or bar appears).
- **Per-game profiles** — save and load named setups.
- **Global hotkeys** — start/stop, panic-stop, and position capture work even while the game is focused.
- **Single instance** — launching again just focuses the running window; it can never spawn duplicates.
- **Fast & light** — near-instant startup, system-tray support, remembers your settings.

---

## ⌨️ Controls & Hotkeys

| Key | Action |
| --- | --- |
| **F6** | Start / Stop (default; changeable, Toggle or Hold mode) |
| **F4** | Capture the cursor position / pick a pixel |
| **F8** | Panic stop (always on) |
| **F9** | Stop recording a macro |

Closing the window hides it to the system tray; right-click the tray icon to quit.

---

## 📥 Download & Install

Grab the latest from the [**Releases**](../../releases) page:

- **`AFKClicker-Setup-vX.Y.exe`** — installer (Start Menu entry, optional desktop shortcut, clean uninstaller). Per-user, no admin needed.
- **`AFKClicker-vX.Y-win64.zip`** — portable. Unzip anywhere and run `AFKClicker.exe`.

**Requirements:** Windows 10/11 (64-bit). Uses the built-in WebView2 runtime (ships with Windows 10/11).

> The build is code-signed. If you ever see a SmartScreen prompt on an unsigned build, choose **More info → Run anyway**.

### Uninstall
- In-app: footer → **Uninstall** (click twice to confirm) — removes the app, shortcuts, and settings.
- Or: Windows **Settings → Apps → AFK Auto Clicker → Uninstall**.

---

## 🎮 Why it works in games

- **Mouse** input is injected with the Win32 `SendInput` API (hardware-level), which DirectX/fullscreen games accept — unlike `PostMessage`-based clickers.
- **Keyboard** input is sent as hardware **scan codes** (`KEYEVENTF_SCANCODE`) — what games read via DirectInput; plain virtual-key events are usually ignored.
- **Hotkeys** read the physical key state (`GetAsyncKeyState`), so they fire even while the game owns the foreground.
- High click rates are honored by raising the system timer resolution to 1 ms while running, and input structs are pre-built so the hot loop allocates nothing.

> Kernel-level anti-cheat (some competitive shooters) can still detect synthetic input. This is for AFK/idle/single-player.

---

## 🧱 Architecture

| File | Purpose |
| --- | --- |
| `engine.py` | All Win32 input: `SendInput`, scan codes, pixel reads, the macro recorder (low-level hooks), and the worker loop. UI-agnostic. |
| `app.py` | The desktop shell — a native WebView2 window via **pywebview**, the JS↔Python bridge (`Api`), global-hotkey thread, system tray, single-instance lock, and self-uninstall. |
| `web/index.html` | The entire UI (HTML/CSS/JS), one self-contained file. |
| `make_icon.py` | Generates `icon.ico`. |
| `package.ps1` | One command → builds the exe (PyInstaller, one-folder) + portable ZIP + Inno Setup installer. |
| `installer.iss` | Inno Setup script (per-user install, dark uninstaller). |

The UI is a thin frontend: every mode compiles to a **program** (a list of steps) that the engine's worker thread loops. Adding a new mode = build a new step list.

---

## 🛠️ Build from source

**Prerequisites:** Windows, Python 3.11+, and (for the installer) [Inno Setup 6](https://jrsoftware.org/isdl.php).

```powershell
# one-time
python -m pip install pywebview pystray pillow pyinstaller

# build exe + portable ZIP + installer
powershell -ExecutionPolicy Bypass -File package.ps1 -Version X.Y

# or just run it during development
python app.py
```

Outputs land in `release/` (`AFKClicker-vX.Y-win64.zip` and `installer/AFKClicker-Setup-vX.Y.exe`).

---

## 📜 License

**Copyright © 2026 Krueger. All rights reserved.** See [LICENSE](LICENSE).
The source is provided for transparency; it is **not** open-source and may not be reused, modified, or redistributed without permission.

---

## ⚖️ Disclaimer

This software automates input. **Many games' Terms of Service prohibit automation**, and using it online may result in account penalties or bans. It is provided "as is", without warranty. You are solely responsible for how you use it. Intended for AFK / idle / single-player scenarios.
