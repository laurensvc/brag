#!/usr/bin/env python3
"""Brag for Windows: the companion (watch.py) in the system tray, with its page in an app window.

  py companion\\desktop.py          run from source (py -m pip install pillow pystray pywebview)
  py companion\\desktop.py --tray   start in the tray, window hidden (what "Start with Windows" runs)
  add --browser                     show the page in your browser instead of a window (automatic without WebView2)
  add --import "<folder>"           copy posting settings and post history from the command-line companion's folder

Closing the window keeps Brag running in the tray; Quit in the tray menu stops it. Settings, the post log and
brag.log live in %APPDATA%\\Brag. windows\\build.ps1 turns this into Brag.exe and BragSetup.exe.
"""
import argparse, ctypes, json, os, shutil, string, sys, threading, time, urllib.request, webbrowser, winreg
from brag_icon import make_icon, write_ico
import watch

APPDATA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Brag")
APP_CONFIG = os.path.join(APPDATA, "brag-app.json")
URL = f"http://127.0.0.1:{watch.PORT}"
# Shared with windows\brag.iss, which can't import them: keep both in step.
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"  # "Start with Windows" (brag.iss [Registry], [Code])
RUN_VALUE = "Brag"
MUTEX = "BragCompanion"  # brag.iss AppMutex: asks you to quit Brag before updating
COLORS = {"ok": (232, 185, 84), "idle": (128, 120, 108), "failed": (239, 107, 91)}  # gold, grey, red
# The Edge WebView2 runtime the window needs; Microsoft's documented way to check it's installed.
WEBVIEW2 = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_DOWNLOAD = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
NOT_WOW = "That isn't a WoW folder. Pick _forever_ in your WoW install: the one with Interface and WTF in it."

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


def parse_args(argv):
    p = argparse.ArgumentParser(prog="Brag", description="Brag for Windows: posts WoW screenshots to Discord.")
    p.add_argument("--tray", action="store_true", help="start in the tray with the window hidden")
    p.add_argument("--browser", action="store_true", help="show the page in your browser instead of a window")
    p.add_argument("--import", dest="import_from", metavar="FOLDER",
                   help="copy posting settings and post history from the command-line companion's folder")
    p.add_argument("--write-icon", metavar="PATH", help=argparse.SUPPRESS)  # used by windows\build.ps1
    return p.parse_known_args(argv)[0]  # tolerate unknown flags: a windowed app has nowhere to print an error


def load_app():
    try:
        with open(APP_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def use_folder(path):
    """Use the WoW folder the player picked or typed (the install folder works too). Returns an error, or None."""
    found = find_game_dir(path) if os.path.isdir(path) else None
    if not found:
        return NOT_WOW
    set_game_dir(found)
    return None


def save_app(**changes):
    watch.write_atomic(APP_CONFIG, json.dumps({**load_app(), **changes}, indent=2))


def import_cli_settings(folders, asked=False):
    """Bring over the command-line companion's posting settings and post history (it keeps them next to
    watch.py), so they carry over to the app. On its own this runs once, on the first start, and only finds them
    when Brag runs from source; asked=True is --import "<folder>". Settings are only copied when the app has none
    of its own; the post history is merged, older entries first. Nothing is moved or deleted.
    Returns what it did, one line per file (also said in the Log)."""
    if load_app().get("importChecked") and not asked:
        return []
    save_app(importChecked=True)
    done = []
    for name, target in (("brag-companion.json", watch.CONFIG), ("brag-log.jsonl", watch.LOG)):
        source = next((os.path.join(f, name) for f in folders if os.path.isfile(os.path.join(f, name))), None)
        if not source or os.path.abspath(source) == os.path.abspath(target):
            continue
        if not os.path.exists(target):
            shutil.copy2(source, target)  # a bad settings file is fine: Brag falls back to the defaults
            done.append(f"Imported {source}")
        elif name == "brag-log.jsonl":
            with watch.LOG_LOCK:  # the app's own entries go last, so they win for the same screenshot
                with open(source, encoding="utf-8", errors="replace") as f:
                    older = f.read()
                with open(target, encoding="utf-8", errors="replace") as f:
                    own = f.read()
                watch.write_atomic(target, older + ("\n" if older and not older.endswith("\n") else "") + own)
            done.append(f"Imported the post history in {source}")
        else:
            done.append(f"Not imported {source}: Brag already has its own posting settings")
    for line in done:
        watch.say(line)
    return done


def set_game_dir(path):
    watch.GAME_DIR = path  # the watcher picks it up within 2 seconds
    save_app(gameDir=path)
    watch.say(f"WoW folder: {path}")
    refresh()


class Api:
    """Called from the page (window.pywebview.api); only exists inside the app window."""

    def choose_folder(self):
        import webview
        picked = window.create_file_dialog(webview.FileDialog.FOLDER, directory=watch.GAME_DIR or "")
        if not picked:
            return None
        error = use_folder(picked[0] if isinstance(picked, (list, tuple)) else picked)
        return {"error": error} if error else {"gameDir": watch.GAME_DIR}


def webview2_installed():
    keys = [(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + WEBVIEW2), (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + WEBVIEW2),
            (winreg.HKEY_CURRENT_USER, "Software\\" + WEBVIEW2)]
    for root, path in keys:
        try:
            with winreg.OpenKey(root, path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
            if version and version != "0.0.0.0":
                return True
        except OSError:
            pass
    return False


# --- Start with Windows ---

def launch_command():
    if getattr(sys, "frozen", False):  # Brag.exe
        return f'"{sys.executable}" --tray'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")  # no console window
    return f'"{pythonw}" "{os.path.abspath(__file__)}" --tray'


def autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
        return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if on:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass


# --- tray ---

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
        icon.notify("Click the Brag icon next to the clock and paste your Discord link under Settings.",
                    "Brag doesn't know where to post yet")
    refresh()


def show(*_):
    if window:
        window.show()
        window.restore()
    else:  # no WebView2: the page opens in the browser
        webbrowser.open(URL)


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
    if window:
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


def message(text, icon=0x10):  # MB_ICONERROR; 0x40 is MB_ICONINFORMATION
    ctypes.windll.user32.MessageBoxW(None, text, "Brag", icon)


def warn_no_webview2():
    """Once per PC: why Brag uses the browser, and how to get its window back."""
    if load_app().get("webview2Warned"):
        return
    save_app(webview2Warned=True)
    message("Brag's window needs Microsoft Edge WebView2, which isn't installed on this PC, so Brag will show its "
            "page in your browser instead. It still runs from the tray as usual.\n\nTo get the window, install "
            f"WebView2 from Microsoft ({WEBVIEW2_DOWNLOAD}) and restart Brag.", 0x40)


def nothing_to_import(folder):
    return f"Nothing to import from {folder}: there's no brag-companion.json or brag-log.jsonl in it."


def second_launch(tray_only, ask_to_show=already_running, tell=message):
    """Brag is already running. Launched by the player: show its window. Launched at login (--tray): do nothing,
    so Windows starting Brag never pops the window up."""
    if tray_only:
        return
    if not ask_to_show():
        tell("Brag is already running: look for its icon in the tray (the ^ next to the clock).")


def log_crashes():
    def report(kind, exc):
        watch.say(f"{kind}: {type(exc).__name__}: {exc}")
    sys.excepthook = lambda t, e, tb: report("Error", e)
    threading.excepthook = lambda a: report(f"Error in {a.thread.name if a.thread else 'thread'}", a.exc_value)


def main():
    global window, icon
    args = parse_args(sys.argv[1:])
    if args.write_icon:
        write_ico(args.write_icon)
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
        if args.import_from:  # the running Brag reads these files fresh, so importing from here works
            done = import_cli_settings([args.import_from], asked=True)
            return message("\n".join(done) or nothing_to_import(args.import_from), 0x40)
        return second_launch(args.tray)
    done = import_cli_settings([args.import_from] if args.import_from else [watch.HERE], asked=bool(args.import_from))
    if args.import_from and not done:
        watch.say(nothing_to_import(args.import_from))
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
    browser = args.browser or not webview2_installed()
    if browser and not args.browser:
        watch.say("Microsoft Edge WebView2 isn't installed: Brag shows its page in your browser")
        warn_no_webview2()
    watch.say(f"Brag started, page at {URL}" + ("" if game else ". Choose your WoW folder under Settings."))
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
    watch.ON_FOLDER = use_folder
    threading.Thread(target=keep_refreshing, daemon=True, name="status").start()
    hidden = args.tray and bool(game)
    if browser:
        if not hidden:
            webbrowser.open(URL)
        icon.run()  # until Quit
        return
    threading.Thread(target=icon.run, daemon=True, name="tray").start()

    window = webview.create_window("Brag", URL, js_api=Api(), width=1280, height=860, min_size=(420, 480),
                                   hidden=hidden, background_color="#14110d")
    window.events.closing += on_closing
    webview.start()  # returns after Quit


if __name__ == "__main__":
    main()
