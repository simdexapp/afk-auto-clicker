"""
AFK Auto Clicker -- input engine (no UI). Shared by the app frontends.

Game-friendly input: mouse via Win32 SendInput, keys via hardware SCAN CODES,
global hotkeys via GetAsyncKeyState, screen pixel reads via GDI GetPixel, and a
low-level-hook macro Recorder. A "program" is a list of step dicts that the
worker thread loops:
    {"action":"mouse", "button","double","fixed","x","y", "delay"}
    {"action":"key",   "key_vk", "delay"}
    {"action":"move",  "dx","dy", "delay"}
    {"action":"wait",  "delay"}
"""

import ctypes
import random
import threading
import time
from ctypes import wintypes

from PIL import Image, ImageDraw

user32 = ctypes.WinDLL("user32", use_last_error=True)
try:
    user32.SetProcessDPIAware()
except Exception:
    pass

if ctypes.sizeof(ctypes.c_void_p) == 8:
    ULONG_PTR = ctypes.c_ulonglong
else:
    ULONG_PTR = ctypes.c_ulong

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT

# winmm timer: Windows' default sleep granularity is ~15.6ms, which caps high
# click rates. timeBeginPeriod(1) drops it to 1ms so small intervals are honored.
winmm = ctypes.WinDLL("winmm", use_last_error=True)


def timer_resolution(on):
    try:
        winmm.timeBeginPeriod(1) if on else winmm.timeEndPeriod(1)
    except Exception:
        pass

gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
gdi32.GetPixel.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
gdi32.GetPixel.restype = wintypes.COLORREF
user32.GetDC.argtypes = (wintypes.HWND,)
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
CLR_INVALID = 0xFFFFFFFF


def _send_mouse(flags):
    inp = INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(0, 0, 0, flags, 0, 0)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _send_key(vk, keyup):
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if keyup else 0)
    if vk in EXTENDED_KEYS:
        flags |= KEYEVENTF_EXTENDEDKEY
    ki = KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    inp = INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=ki))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def press_key(vk):
    _send_key(vk, False)
    _send_key(vk, True)


def get_cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def key_is_down(vk):
    return (user32.GetAsyncKeyState(vk) & 0x8000) != 0


def get_pixel(x, y):
    hdc = user32.GetDC(0)
    if not hdc:
        return None
    try:
        c = gdi32.GetPixel(hdc, int(x), int(y))
    finally:
        user32.ReleaseDC(0, hdc)
    if c == CLR_INVALID:
        return None
    return (c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF)


def condition_met(cond):
    rgb = get_pixel(cond["x"], cond["y"])
    if rgb is None:
        return False
    tol = int(round(cond.get("tol", 0) * 2.55))
    target = cond["rgb"]
    return all(abs(rgb[i] - target[i]) <= tol for i in range(3))


BUTTONS = {
    "Left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "Right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "Middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}
VK_MAP = {f"F{i}": 0x70 + (i - 1) for i in range(1, 13)}
VK_F8_PANIC = 0x77

KEY_MAP = {}
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEY_MAP[_c] = ord(_c)
for _d in "0123456789":
    KEY_MAP[_d] = ord(_d)
KEY_MAP.update({"Space": 0x20, "Enter": 0x0D, "Tab": 0x09, "Esc": 0x1B,
                "Backspace": 0x08, "Shift": 0x10, "Ctrl": 0x11, "Alt": 0x12,
                "Up": 0x26, "Down": 0x28, "Left": 0x25, "Right": 0x27})
for _i in range(1, 13):
    KEY_MAP[f"F{_i}"] = 0x70 + (_i - 1)
EXTENDED_KEYS = {0x25, 0x26, 0x27, 0x28}
VK_TO_NAME = {v: k for k, v in KEY_MAP.items()}
KEY_NAMES = (["Space", "Enter", "Tab", "Esc", "Shift", "Ctrl", "Alt",
              "Up", "Down", "Left", "Right"]
             + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + list("0123456789")
             + [f"F{i}" for i in range(1, 13)])


def key_name(vk):
    return VK_TO_NAME.get(vk, f"0x{vk:X}")


# --- worker engine ---
clicking = threading.Event()
stop_app = threading.Event()
RUN = {}
CLICK_COUNT = 0


# Pre-built input arrays so the hot loop allocates nothing and sends down+up in
# a SINGLE SendInput syscall instead of two.
_ISZ = ctypes.sizeof(INPUT)
_MOUSE_PAIRS = {}
for _name, (_d, _u) in BUTTONS.items():
    _MOUSE_PAIRS[_name] = (INPUT * 2)(
        INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(0, 0, 0, _d, 0, 0))),
        INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(0, 0, 0, _u, 0, 0))))
_KEY_CACHE = {}


def _key_pair(vk):
    arr = _KEY_CACHE.get(vk)
    if arr is None:
        scan = user32.MapVirtualKeyW(vk, 0)
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_KEYS else 0)
        arr = (INPUT * 2)(
            INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(0, scan, flags, 0, 0))),
            INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(0, scan, flags | KEYEVENTF_KEYUP, 0, 0))))
        _KEY_CACHE[vk] = arr
    return arr


def execute_step(step):
    a = step["action"]
    if a == "wait":
        return
    if a == "key":
        user32.SendInput(2, _key_pair(step["key_vk"]), _ISZ)
        return
    if a == "move":
        x, y = get_cursor_pos()
        user32.SetCursorPos(x + step.get("dx", 0), y + step.get("dy", 0))
        return
    if step.get("fixed"):
        user32.SetCursorPos(step.get("x", 0), step.get("y", 0))
    pair = _MOUSE_PAIRS[step.get("button", "Left")]
    user32.SendInput(2, pair, _ISZ)
    if step.get("double"):
        user32.SendInput(2, pair, _ISZ)


def _interruptible_sleep(duration):
    if duration <= 0:
        return
    end = time.perf_counter() + duration
    while True:
        remaining = end - time.perf_counter()
        if remaining <= 0 or not clicking.is_set() or stop_app.is_set():
            return
        time.sleep(min(0.01, remaining))


def worker_loop():
    global CLICK_COUNT
    hi_res = False
    while not stop_app.is_set():
        if not clicking.is_set():
            if hi_res:
                timer_resolution(False)   # restore default timer when idle
                hi_res = False
            CLICK_COUNT = 0
            clicking.wait(timeout=0.2)
            continue
        if not hi_res:
            timer_resolution(True)        # 1ms timer for accurate high rates
            hi_res = True

        program = RUN.get("program") or []
        if not program:
            clicking.clear()
            continue
        cond = RUN.get("condition")
        if cond and not condition_met(cond):
            _interruptible_sleep(0.03)
            continue

        jitter = RUN.get("jitter", 0)
        is_set = clicking.is_set
        stopped = stop_app.is_set
        count = CLICK_COUNT
        completed_loop = True
        for step in program:
            if not is_set() or stopped():
                completed_loop = False
                break
            execute_step(step)
            count += 1
            delay = step.get("delay", 0.0)
            if jitter > 0 and delay > 0:
                spread = delay * jitter
                delay = max(0.0, delay + random.uniform(-spread, spread))
            if delay:
                _interruptible_sleep(delay)
        CLICK_COUNT = count
        if completed_loop:
            RUN["_loops"] = RUN.get("_loops", 0) + 1
            if RUN.get("limit") and RUN["_loops"] >= RUN["limit"]:
                clicking.clear()


def make_icon_image(size=64, accent=(124, 92, 255, 255)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, size - 2, size - 2], radius=size // 5, fill=accent)
    s = size
    d.polygon([(s * 0.30, s * 0.20), (s * 0.30, s * 0.76), (s * 0.44, s * 0.63),
               (s * 0.53, s * 0.82), (s * 0.62, s * 0.78), (s * 0.53, s * 0.59),
               (s * 0.70, s * 0.59)], fill=(255, 255, 255, 255))
    return img


# --- macro recorder (low-level hooks on a message-pump thread; F9 stops) ---
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_QUIT = 0x0012
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN = 0x0201, 0x0204, 0x0207
VK_F9 = 0x78

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.CFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.GetMessageW.argtypes = (ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class Recorder:
    def __init__(self):
        self.recording = False
        self.events = []
        self.on_done = None
        self._tid = None
        self._down = set()
        self._mouse_proc = None
        self._kb_proc = None
        self._hm = None
        self._hk = None

    def start(self):
        if self.recording:
            return
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        if self.recording and self._tid:
            self.recording = False
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)

    def _add(self, step):
        self.events.append((time.perf_counter(), step))

    def _on_mouse(self, nCode, wParam, lParam):
        if nCode >= 0 and self.recording and wParam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN):
            ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            btn = {WM_LBUTTONDOWN: "Left", WM_RBUTTONDOWN: "Right", WM_MBUTTONDOWN: "Middle"}[wParam]
            self._add({"action": "mouse", "button": btn, "fixed": True, "x": ms.pt.x, "y": ms.pt.y})
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _on_kb(self, nCode, wParam, lParam):
        if nCode >= 0 and self.recording:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if vk == VK_F9:
                    self.recording = False
                    user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
                elif vk not in self._down:
                    self._down.add(vk)
                    self._add({"action": "key", "key_vk": vk})
            elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                self._down.discard(vk)
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _run(self):
        self._tid = kernel32.GetCurrentThreadId()
        self.events = []
        self._down = set()
        self.recording = True
        self._mouse_proc = HOOKPROC(self._on_mouse)
        self._kb_proc = HOOKPROC(self._on_kb)
        self._hm = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc, None, 0)
        self._hk = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, None, 0)
        msg = wintypes.MSG()
        while self.recording and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if self._hm:
            user32.UnhookWindowsHookEx(self._hm)
        if self._hk:
            user32.UnhookWindowsHookEx(self._hk)
        self.recording = False
        if self.on_done:
            self.on_done()

    def to_steps(self):
        evs = self.events
        steps = []
        for i, (t, s) in enumerate(evs):
            s = dict(s)
            s["delay"] = round(evs[i + 1][0] - t, 3) if i < len(evs) - 1 else 0.2
            steps.append(s)
        return steps
