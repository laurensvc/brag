#!/usr/bin/env python3
"""Brag for Windows: the companion (watch.py) in the system tray, with its page in an app window.

  py companion\\desktop.py          run from source (py -m pip install pillow pystray pywebview)
  py companion\\desktop.py --tray   start in the tray, window hidden (what "Start with Windows" runs)

Closing the window keeps Brag running in the tray; Quit in the tray menu stops it. Settings, the post log and
brag.log live in %APPDATA%\\Brag. windows\\build.ps1 turns this into Brag.exe and BragSetup.exe.
"""
import ctypes, json, os, string, sys, threading, time, urllib.request, winreg
from PIL import Image, ImageDraw, ImageFont
import watch

APPDATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Brag")
APP_CONFIG = os.path.join(APPDATA, "brag-app.json")
URL = f"http://127.0.0.1:{watch.PORT}"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MUTEX = "BragCompanion"  # windows\brag.iss uses it too, to ask you to quit Brag before updating
COLORS = {"ok": (232, 185, 84), "idle": (128, 120, 108), "failed": (239, 107, 91)}  # gold, grey, red

window = icon = None
ICONS = {}  # tray icon image per color name, made at startup
icon_color = None  # the color name the tray icon shows now
warned_no_webhook = False  # the "no webhook yet" notification shows once per session
quitting = False


# --- the WoW folder ---

def find_game_dir(path):
    """The folder Brag needs (it has WTF or Interface in it), from what the person picked; None if it's not WoW."""
    for p in (path, os.path.join(path, "_forever_")):  # accept the install folder too
        if any(os.path.isdir(os.path.join(p, d)) for d in ("WTF", "Interface")):
            return os.path.normpath(p)
    return None


def detect_game_dir():
    """Look in the usual install places, so most people never see the folder picker."""
    drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.isdir(f"{d}:\\")]
    for drive in drives:
        for base in (r"Program Files (x86)\World of Warcraft", r"Program Files\World of Warcraft",
                     r"World of Warcraft", r"Games\World of Warcraft"):
            found = find_game_dir(os.path.join(drive, base, "_forever_"))
            if found:
                return found
    return None


def load_app():
    try:
        with open(APP_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def set_game_dir(path):
    watch.GAME_DIR = path  # the watcher picks it up within 2 seconds
    watch.write_atomic(APP_CONFIG, json.dumps({**load_app(), "gameDir": path}, indent=2))
    watch.say(f"WoW folder: {path}")
    refresh()


class Api:
    """Called from the page (window.pywebview.api); only exists inside the app window."""

    def choose_folder(self):
        import webview
        picked = window.create_file_dialog(webview.FileDialog.FOLDER, directory=watch.GAME_DIR or "")
        if not picked:
            return None
        path = find_game_dir(picked[0] if isinstance(picked, (list, tuple)) else picked)
        if not path:
            return {"error": "That isn't a WoW folder. Pick _forever_ in your WoW install: the one with Interface and WTF in it."}
        set_game_dir(path)
        return {"gameDir": path}


# --- Start with Windows ---

def launch_command():
    if getattr(sys, "frozen", False):  # Brag.exe
        return f'"{sys.executable}" --tray'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")  # no console window
    return f'"{pythonw}" "{os.path.abspath(__file__)}" --tray'


def autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, "Brag")
        return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if on:
            winreg.SetValueEx(key, "Brag", 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, "Brag")
            except FileNotFoundError:
                pass


# --- tray ---

def make_icon(color, size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, size - 2, size - 2], radius=size // 5, fill=color)
    try:
        font = ImageFont.truetype("segoeuib.ttf", int(size * 0.72))  # Segoe UI Bold, on every Windows
    except OSError:
        font = ImageFont.load_default(size=int(size * 0.72))
    d.text((size / 2, size / 2), "B", font=font, fill=(26, 20, 8), anchor="mm")
    return img


def tray_state():
    """(icon color, tooltip) from the companion's status, which the page shows too."""
    kind, message = watch.status()
    color = kind if kind in ("ok", "failed") else "idle"
    return color, ("Brag: " + message)[:127]  # Windows cuts tooltips at 127 characters


def refresh():
    global icon_color
    if not icon:
        return
    try:
        color, title = tray_state()
    except Exception as e:  # a half-written SavedVariables file: try again next time
        watch.say(f"Status check failed: {e}")
        return
    if icon.title != title:
        icon.title = title
    if icon_color != color:
        icon.icon, icon_color = ICONS[color], color


def keep_refreshing():
    while True:
        refresh()  # catches changes made in WoW (the webhook, Enabled) without a post
        time.sleep(5)


def on_result(name, result, text):
    global warned_no_webhook
    if result.kind == "failed":
        icon.notify(f"{text or name}\n{result.reason}"[:250], "Brag couldn't post a screenshot")
    elif result == watch.NO_WEBHOOK and not warned_no_webhook:
        warned_no_webhook = True  # once per session: every screenshot would say the same
        icon.notify("Type /brag in WoW, paste your Discord webhook, then Save & reload.", "Brag has no webhook yet")
    refresh()


def show(*_):
    if window:
        window.show()
        window.restore()


def toggle_pause(*_):
    if watch.PAUSED.is_set():
        watch.PAUSED.clear()
        watch.say("Posting resumed")
    else:
        watch.PAUSED.set()
        watch.say("Posting paused: new screenshots are skipped")
    refresh()


def open_screenshots(*_):
    folder = watch.screenshots_dir(watch.GAME_DIR)
    os.makedirs(folder, exist_ok=True)
    os.startfile(folder)


def quit_app(*_):
    global quitting
    quitting = True
    icon.stop()
    window.destroy()


def on_closing():
    if quitting:
        return True
    threading.Thread(target=window.hide, daemon=True).start()  # not from inside the closing event
    return False  # keep running in the tray


# --- startup ---

def already_running():
    """Ask a running Brag to show its window. True if one answered."""
    req = urllib.request.Request(URL + "/api/show", data=b"{}", method="POST", headers={"Origin": URL})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except OSError:
        return False


def message(text):
    ctypes.windll.user32.MessageBoxW(None, text, "Brag", 0x10)  # MB_ICONERROR


def log_crashes():
    def report(kind, exc):
        watch.say(f"{kind}: {type(exc).__name__}: {exc}")
    sys.excepthook = lambda t, e, tb: report("Error", e)
    threading.excepthook = lambda a: report(f"Error in {a.thread.name if a.thread else 'thread'}", a.exc_value)


def main():
    global window, icon
    if "--write-icon" in sys.argv:  # used by windows\build.ps1
        path = sys.argv[sys.argv.index("--write-icon") + 1]
        make_icon(COLORS["ok"], 256).save(path, sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
        return
    import pystray, webview  # only needed for the app itself, not for --write-icon

    if sys.stdout:
        sys.stdout.reconfigure(errors="replace")
    os.makedirs(APPDATA, exist_ok=True)
    watch.LOG = os.path.join(APPDATA, "brag-log.jsonl")
    watch.CONFIG = os.path.join(APPDATA, "brag-companion.json")
    watch.TEXT_LOG = os.path.join(APPDATA, "brag.log")
    if os.path.exists(watch.TEXT_LOG) and os.path.getsize(watch.TEXT_LOG) > 1_000_000:
        os.replace(watch.TEXT_LOG, watch.TEXT_LOG + ".old")  # keep brag.log small
    log_crashes()

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    mutex = kernel32.CreateMutexW(None, False, MUTEX)  # held until Brag exits
    if mutex and ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: Brag is running
        if not already_running():
            message("Brag is already running: look for its icon in the tray (the ^ next to the clock).")
        return
    saved = load_app().get("gameDir")
    game = find_game_dir(saved) if saved and os.path.isdir(saved) else None
    try:
        server = watch.start(game)
    except OSError:
        message(f"Brag can't start: another program is using port {watch.PORT}.")
        return
    if not game:
        game = detect_game_dir()
        if game:
            set_game_dir(game)
    watch.say(f"Brag started, page at {URL}" + ("" if game else ". Choose your WoW folder in the window."))
    threading.Thread(target=server.serve_forever, daemon=True, name="page").start()

    ICONS.update({k: make_icon(c) for k, c in COLORS.items()})
    icon = pystray.Icon("Brag", ICONS["idle"], "Brag", pystray.Menu(
        pystray.MenuItem("Open Brag", show, default=True),  # also a left click on the icon
        pystray.MenuItem("Pause posting", toggle_pause, checked=lambda _: watch.PAUSED.is_set()),
        pystray.MenuItem("Open Screenshots folder", open_screenshots, enabled=lambda _: bool(watch.GAME_DIR)),
        pystray.MenuItem("Start with Windows", lambda: set_autostart(not autostart()), checked=lambda _: autostart()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    ))
    watch.LISTENERS.append(on_result)
    watch.ON_SHOW = show
    threading.Thread(target=icon.run, daemon=True, name="tray").start()
    threading.Thread(target=keep_refreshing, daemon=True, name="status").start()

    window = webview.create_window("Brag", URL, js_api=Api(), width=1280, height=860, min_size=(420, 480),
                                   hidden="--tray" in sys.argv and bool(game), background_color="#14110d")
    window.events.closing += on_closing
    webview.start()  # returns after Quit


if __name__ == "__main__":
    main()
