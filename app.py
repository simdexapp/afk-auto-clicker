"""
AFK Auto Clicker -- premium WebView2 frontend (pywebview).

The UI is HTML/CSS/JS rendered in a native Edge WebView2 window; all input,
recording, pixel reads and hotkeys live in engine.py (Python). JS talks to
Python through `Api` (window.pywebview.api.*). Global hotkeys + the worker run
on background threads; JS polls api.get_state() to stay in sync.

Build:  python -m PyInstaller --onefile --windowed --name AFKClicker --icon icon.ico ^
            --add-data "icon.ico;." --add-data "web;web" ^
            --collect-all webview --hidden-import pystray._win32 app.py
"""

import ctypes
import json
import os
import subprocess
import sys
import threading
import time

import webview
import pystray

import engine

APP_NAME = "AFK Auto Clicker"
APP_VERSION = "4.1"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".afk_autoclicker_v3.json")

VK_F4 = 0x73
VK_F8 = 0x77


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# ---------------------------------------------------------------------------
# Single-instance lock: only ONE copy of the app may run. A second launch
# detects the existing instance, brings its window to the front, and exits --
# so spam-clicking the icon can never spawn a pile of apps.
# ---------------------------------------------------------------------------
_MUTEX_NAME = "AFKAutoClicker_SingleInstance_v1"
_ERROR_ALREADY_EXISTS = 183
_mutex_handle = None


def acquire_single_instance():
    """Return True if we are the first/only instance, False if one is already running."""
    global _mutex_handle
    k = engine.kernel32
    k.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    k.CreateMutexW.restype = ctypes.c_void_p
    handle = k.CreateMutexW(None, 0, _MUTEX_NAME)
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        return False
    _mutex_handle = handle  # keep a reference so the OS holds the lock for our lifetime
    return True


def focus_existing_instance():
    """Bring the already-running app's window to the foreground."""
    try:
        u = engine.user32
        u.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
        u.FindWindowW.restype = ctypes.c_void_p
        hwnd = u.FindWindowW(None, APP_NAME)
        if hwnd:
            u.ShowWindow(hwnd, 9)            # SW_RESTORE
            u.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _hex_to_rgb(h):
    h = (h or "#000000").lstrip("#")
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except Exception:
        return (0, 0, 0)


def _load():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save(data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


def build_program(s):
    """Turn the JS settings dict into (program, limit, jitter, condition)."""
    s = s or {}
    mode = s.get("mode", "click")
    if mode == "macro":
        steps = s.get("macro_steps") or []
        if not steps:
            raise ValueError("Add at least one macro step first.")
        prog = [dict(x) for x in steps]
        limit = int(s.get("macro_count", 0)) if s.get("macro_repeat") == "count" else 0
        return prog, limit, 0.0, None

    if mode == "afk":
        interval = max(1, int(s.get("afk_interval", 60)))
        jit = max(0, min(90, int(s.get("afk_jitter", 0)))) / 100.0
        if s.get("afk_method") == "key":
            vk = engine.KEY_MAP.get(s.get("afk_key", "Space"), 0x20)
            return [{"action": "key", "key_vk": vk, "delay": float(interval)}], 0, jit, None
        return ([{"action": "move", "dx": 4, "dy": 0, "delay": 0.08},
                 {"action": "move", "dx": -4, "dy": 0, "delay": float(interval)}], 0, jit, None)

    # click
    jit = max(0, min(90, int(s.get("jitter", 0)))) / 100.0
    interval = max(0, int(s.get("interval_ms", 100))) / 1000.0
    if s.get("action") == "key":
        step = {"action": "key", "key_vk": engine.KEY_MAP.get(s.get("key", "Space"), 0x20),
                "delay": interval}
    else:
        step = {"action": "mouse", "button": s.get("button", "Left"), "double": bool(s.get("double")),
                "fixed": s.get("pos") == "fixed", "x": int(s.get("x", 0)), "y": int(s.get("y", 0)),
                "delay": interval}
    limit = int(s.get("count", 0)) if s.get("repeat") == "count" else 0
    cond = None
    if s.get("px_enabled"):
        cond = {"x": int(s.get("px_x", 0)), "y": int(s.get("px_y", 0)),
                "rgb": _hex_to_rgb(s.get("px_color", "#000000")), "tol": int(s.get("px_tol", 0))}
    return [step], limit, jit, cond


class Api:
    def __init__(self):
        self.settings = {}
        self.window = None
        self.icon = None
        self._really_quit = False
        self.capture_kind = None
        self.capture_token = 0
        self.capture_result = None
        self.recorded_token = 0
        self.recorded = None
        self.last_error = ""
        self.recorder = engine.Recorder()
        self.recorder.on_done = self._on_record_done

    # ---- startup data ----
    def get_initial(self):
        data = _load()
        return {
            "version": APP_VERSION,
            "settings": data.get("current"),
            "profiles": sorted(data.get("profiles", {}).keys()),
            "last": data.get("last", ""),
            "key_map": engine.KEY_MAP,
            "key_names": engine.KEY_NAMES,
            "buttons": list(engine.BUTTONS.keys()),
            "hotkeys": list(engine.VK_MAP.keys()),
        }

    # ---- live state (polled by JS) ----
    def get_state(self):
        return {
            "running": engine.clicking.is_set(),
            "count": engine.CLICK_COUNT,
            "recording": self.recorder.recording,
            "capture_token": self.capture_token,
            "capture": self.capture_result,
            "recorded_token": self.recorded_token,
            "recorded": self.recorded,
            "error": self.last_error,
        }

    def set_settings(self, s):
        self.settings = s or {}
        return True

    # ---- run control ----
    def start(self, s=None):
        if s is not None:
            self.settings = s
        return self._do_start()

    def _do_start(self):
        if engine.clicking.is_set():
            return True
        if self.recorder.recording:
            self.last_error = "Stop recording first."
            return False
        try:
            prog, limit, jit, cond = build_program(self.settings)
        except ValueError as e:
            self.last_error = str(e)
            return False
        except Exception:
            self.last_error = "Check your numbers."
            return False
        self.last_error = ""
        engine.RUN.clear()
        engine.RUN.update({"program": prog, "limit": limit, "jitter": jit,
                           "condition": cond, "_loops": 0})
        engine.clicking.set()
        return True

    def stop(self):
        engine.clicking.clear()
        return True

    def toggle(self):
        return self.stop() if engine.clicking.is_set() else self._do_start()

    # ---- capture / pixel ----
    def arm_capture(self, kind):
        self.capture_kind = kind
        return True

    def pick_pixel_now(self):
        x, y = engine.get_cursor_pos()
        rgb = engine.get_pixel(x, y) or (0, 0, 0)
        return {"x": x, "y": y, "color": "#%02x%02x%02x" % rgb}

    # ---- recorder ----
    def record_start(self):
        if engine.clicking.is_set():
            self.last_error = "Stop the clicker first."
            return False
        self.recorder.start()
        return True

    def record_stop(self):
        self.recorder.stop()
        return True

    def _on_record_done(self):
        self.recorded = self.recorder.to_steps()
        self.recorded_token += 1

    # ---- profiles ----
    def save_profile(self, name, s):
        d = _load()
        d.setdefault("profiles", {})[name] = s
        d["last"] = name
        _save(d)
        return sorted(d["profiles"].keys())

    def load_profile(self, name):
        return _load().get("profiles", {}).get(name)

    def delete_profile(self, name):
        d = _load()
        d.get("profiles", {}).pop(name, None)
        _save(d)
        return sorted(d.get("profiles", {}).keys())

    def _persist_current(self):
        if self.settings:
            d = _load()
            d["current"] = self.settings
            _save(d)

    # ---- window ----
    def minimize(self):
        try:
            self.window.minimize()
        except Exception:
            pass
        return True

    def hide(self):
        self._persist_current()
        try:
            self.window.hide()
        except Exception:
            pass
        return True

    def quit(self):
        self._persist_current()
        self._shutdown()
        return True

    def _shutdown(self):
        self._really_quit = True
        engine.clicking.clear()
        engine.stop_app.set()
        try:
            self.recorder.stop()
        except Exception:
            pass
        try:
            if self.icon:
                self.icon.stop()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass

    def uninstall(self):
        """Remove the app from the PC: run the installer's uninstaller (or self-
        delete if portable), wipe the settings file, then quit."""
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        unins = os.path.join(exe_dir, "unins000.exe")
        frozen = getattr(sys, "frozen", False)
        # wipe settings (both the current and legacy config files)
        for p in (CONFIG_PATH, os.path.join(os.path.expanduser("~"), ".afk_autoclicker.json")):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        NO_WINDOW = 0x08000000
        try:
            if os.path.exists(unins):
                # let us fully exit first, then the official uninstaller runs
                subprocess.Popen('cmd /c timeout /t 1 >nul & "%s"' % unins,
                                 shell=True, creationflags=NO_WINDOW)
            elif frozen:
                # portable build: delete our own folder after we exit
                subprocess.Popen('cmd /c timeout /t 2 >nul & rmdir /s /q "%s"' % exe_dir,
                                 shell=True, creationflags=NO_WINDOW)
        except Exception:
            pass
        self._shutdown()
        return True


def hotkey_loop(api):
    prev_toggle = False
    prev_f4 = False
    while not engine.stop_app.is_set():
        if api.recorder.recording:
            time.sleep(0.03)
            continue
        if engine.key_is_down(VK_F8) and engine.clicking.is_set():
            engine.clicking.clear()

        f4 = engine.key_is_down(VK_F4)
        if f4 and not prev_f4 and api.capture_kind:
            x, y = engine.get_cursor_pos()
            res = {"kind": api.capture_kind, "x": x, "y": y}
            if api.capture_kind == "pixel":
                rgb = engine.get_pixel(x, y) or (0, 0, 0)
                res["color"] = "#%02x%02x%02x" % rgb
            api.capture_result = res
            api.capture_token += 1
            api.capture_kind = None
        prev_f4 = f4

        s = api.settings or {}
        vk = engine.VK_MAP.get(s.get("hotkey", "F6"), 0x75)
        down = engine.key_is_down(vk)
        if s.get("trigger") == "hold":
            if down and not engine.clicking.is_set():
                api._do_start()
            elif not down and engine.clicking.is_set():
                engine.clicking.clear()
        else:
            if down and not prev_toggle:
                api.toggle()
        prev_toggle = down
        time.sleep(0.015)


def tray_thread(api):
    menu = pystray.Menu(
        pystray.MenuItem("Show", lambda icon, item: api.window.show(), default=True),
        pystray.MenuItem(lambda item: "Stop" if engine.clicking.is_set() else "Start",
                         lambda icon, item: api.toggle()),
        pystray.MenuItem("Quit", lambda icon, item: api.quit()),
    )
    api.icon = pystray.Icon("afk_autoclicker", engine.make_icon_image(), APP_NAME, menu)
    api.icon.run()


def main():
    # Refuse to start a second copy -- just surface the one already running.
    if not acquire_single_instance():
        focus_existing_instance()
        return

    api = Api()
    threading.Thread(target=engine.worker_loop, daemon=True).start()
    threading.Thread(target=hotkey_loop, args=(api,), daemon=True).start()

    with open(resource_path(os.path.join("web", "index.html")), "r", encoding="utf-8") as fh:
        html = fh.read()

    window = webview.create_window(
        APP_NAME, html=html, js_api=api,
        width=480, height=812, resizable=False, frameless=False,
        background_color="#0c0c0e", min_size=(480, 560),
    )
    api.window = window

    def on_closing():
        if api._really_quit:
            return True
        api.hide()
        return False

    window.events.closing += on_closing
    window.events.shown += lambda: _set_dark_titlebar()
    threading.Thread(target=tray_thread, args=(api,), daemon=True).start()
    webview.start()


def _set_dark_titlebar():
    """Make the native title bar dark to match the app (Win10 2004+/Win11)."""
    try:
        u = engine.user32
        u.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
        u.FindWindowW.restype = ctypes.c_void_p
        hwnd = u.FindWindowW(None, APP_NAME)
        if not hwnd:
            return
        dwm = ctypes.WinDLL("dwmapi")
        val = ctypes.c_int(1)
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


if __name__ == "__main__":
    main()
