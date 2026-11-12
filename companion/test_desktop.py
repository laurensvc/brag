# Windows only: the tray app's own logic (the window and tray icon themselves are checked by hand).
import os, struct, sys, tempfile, urllib.request
from PIL import Image
import desktop, watch

with tempfile.TemporaryDirectory() as d:
    game = os.path.join(d, "World of Warcraft", "_forever_")
    os.makedirs(os.path.join(game, "WTF"))
    assert desktop.find_game_dir(game) == game
    assert desktop.find_game_dir(os.path.dirname(game)) == game  # the install folder works too
    assert desktop.find_game_dir(d) is None
    # the folder the player typed or picked
    assert desktop.use_folder(d) == desktop.NOT_WOW and desktop.use_folder(os.path.join(d, "nope")) == desktop.NOT_WOW
    real_set, set_to = desktop.set_game_dir, []
    desktop.set_game_dir = set_to.append
    try:
        assert desktop.use_folder(os.path.dirname(game)) is None and set_to == [game]
    finally:
        desktop.set_game_dir = real_set

    # the tray shows the companion's status: gold when all is well, red after a failure, grey otherwise
    watch.GAME_DIR = None
    assert desktop.tray_state() == ("idle", "Brag: Step 1: choose your WoW folder under Settings.")
    watch.GAME_DIR = game
    watch.install_addon(game)
    saved = os.path.join(game, "WTF", "Account", "ME", "SavedVariables")
    os.makedirs(saved)
    with open(os.path.join(saved, "Brag.lua"), "w") as f:
        f.write('BragDB = {\n["webhook"] = "https://discord.com/api/webhooks/1/abc",\n["enabled"] = true,\n}\n')
    assert desktop.tray_state() == ("ok", "Brag: Ready. Play WoW: your big moments get posted to Discord.")
    watch.remember(watch.Result("failed", "webhook was deleted (HTTP 404) " + "x" * 200))
    color, tip = desktop.tray_state()
    assert color == "failed" and tip.startswith("Brag: Last post failed: webhook was deleted") and len(tip) == 127
    watch.PAUSED.set()
    assert desktop.tray_state()[0] == "idle"
    watch.PAUSED.clear()
    watch.GAME_DIR, watch.LAST_FAILURE = None, None

# "Start with Windows" runs Brag in the tray, without a console window
assert desktop.launch_command().endswith('desktop.py" --tray') and "pythonw.exe" in desktop.launch_command()
for color in desktop.COLORS.values():
    for size in (16, 24, 32, 64, 256):
        icon = desktop.make_icon(color, size)
        assert icon.size == (size, size) and icon.mode == "RGBA"
        assert icon.getpixel((0, size - 1))[3] == 0
        # Check the unblended rim; small exports also blend it into the dark field.
        if size == 256:
            assert icon.getpixel((size // 2, size // 8))[:3] == color
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "brag.ico")
    desktop.write_ico(path)
    with Image.open(path) as ico:
        assert ico.ico.sizes() == {(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)}
        with Image.open(os.path.join(watch.ASSETS, "brag.ico")) as shipped:
            assert shipped.ico.sizes() == ico.ico.sizes()
            assert shipped.tobytes() == ico.tobytes()
with open(os.path.join(watch.ADDON, "icon.tga"), "rb") as f:
    header = f.read(18)
    assert header[2] == 2  # uncompressed true-color
    assert struct.unpack_from("<HH", header, 12) == (64, 64)
    assert header[16] == 32 and header[17] & 15 == 8  # RGBA, 8 alpha bits
with Image.open(os.path.join(watch.ADDON, "icon.tga")) as texture:
    assert texture.mode == "RGBA" and texture.tobytes() == desktop.make_icon(desktop.COLORS["ok"]).tobytes()

# a second launch while Brag runs: the player's launch shows the window, a login launch stays quiet
asked, told = [], []
desktop.second_launch(True, lambda: asked.append(1) or True, told.append)
assert asked == [] and told == []
desktop.second_launch(False, lambda: asked.append(1) or True, told.append)
assert asked == [1] and told == []
desktop.second_launch(False, lambda: False, told.append)  # the running Brag didn't answer
assert told and "already running" in told[0]

assert desktop.webview2_installed() in (True, False)  # reads the registry; Windows 11 always has it

# without WebView2 the player is told once per PC, not on every start
with tempfile.TemporaryDirectory() as d:
    real = desktop.APP_CONFIG, desktop.message
    told = []
    desktop.APP_CONFIG, desktop.message = os.path.join(d, "brag-app.json"), lambda text, icon=0: told.append(text)
    try:
        desktop.warn_no_webview2()
        desktop.warn_no_webview2()
        assert len(told) == 1 and "WebView2" in told[0] and desktop.load_app()["webview2Warned"] is True
    finally:
        desktop.APP_CONFIG, desktop.message = real

# a command-line companion's posting settings and post log carry over to the app, once, without overwriting
with tempfile.TemporaryDirectory() as cli, tempfile.TemporaryDirectory() as app:
    real = desktop.APP_CONFIG, watch.CONFIG, watch.LOG
    desktop.APP_CONFIG = os.path.join(app, "brag-app.json")
    watch.CONFIG, watch.LOG = os.path.join(app, "brag-companion.json"), os.path.join(app, "brag-log.jsonl")
    try:
        with open(os.path.join(cli, "brag-companion.json"), "w") as f:
            f.write('{"caption": false, "retries": 1, "maxHeight": 720, "jpegQuality": 75, "keepDays": 30, "deleteShots": false}')
        with open(os.path.join(cli, "brag-log.jsonl"), "w") as f:
            f.write('{"name": "a.jpg", "status": "posted", "caption": "", "time": 1}\n')
        assert len(desktop.import_cli_settings([cli])) == 2
        assert watch.load_companion()["keepDays"] == 30 and watch.statuses()["a.jpg"]["kind"] == "posted"
        assert any(line["text"].startswith("Imported ") for line in watch.LINES)
        assert os.path.exists(os.path.join(cli, "brag-companion.json"))  # copied, not moved

        with open(os.path.join(cli, "brag-companion.json"), "w") as f:
            f.write('{"keepDays": 99}')
        assert desktop.import_cli_settings([cli]) == []  # on its own, only on the first start
        with open(watch.LOG, "a") as f:
            f.write('{"name": "a.jpg", "status": "failed: x", "caption": "", "time": 2}\n')  # the app posted since
        done = desktop.import_cli_settings([cli], asked=True)  # --import: settings kept, history merged
        assert done[0].startswith("Not imported") and done[1].startswith("Imported the post history")
        assert watch.load_companion()["keepDays"] == 30
        assert watch.statuses()["a.jpg"]["kind"] == "failed"  # the app's own entry wins

        os.remove(watch.CONFIG)
        with open(os.path.join(cli, "brag-companion.json"), "w") as f:
            f.write("{not json")
        assert desktop.import_cli_settings([cli], asked=True)[0].startswith("Imported ")
        assert watch.load_companion() == watch.COMPANION_DEFAULTS  # a corrupt file: defaults, no crash
        assert desktop.import_cli_settings([os.path.join(cli, "missing")], asked=True) == []
    finally:
        desktop.APP_CONFIG, watch.CONFIG, watch.LOG = real

# command line
a = desktop.parse_args(["--tray", "--import", "C:/old brag/companion", "--unknown"])
assert a.tray and not a.browser and a.import_from == "C:/old brag/companion" and a.write_icon is None
assert not desktop.parse_args([]).tray

# updates: the newest GitHub release's BragSetup.exe, offered when it's newer than this Brag
asset = {"name": "BragSetup.exe", "browser_download_url": "https://github.com/x/BragSetup.exe"}
assert desktop.setup_in({"tag_name": "v1.10.0", "assets": [{"name": "Brag-1.10.0.zip"}, asset]}) == \
    ("1.10.0", "https://github.com/x/BragSetup.exe")
assert desktop.setup_in({"tag_name": "v1.10.0", "assets": [{"name": "Brag-1.10.0.zip"}]}) is None
assert desktop.setup_in({}) is None
assert desktop.APP_VERSION and desktop.APP_VERSION == watch.addon_version(watch.ADDON)
real_version = desktop.APP_VERSION
desktop.APP_VERSION = "1.9.0"
try:
    current = ("current", "You have the newest Brag (1.9.0).")
    assert desktop.check_for_update(lambda: ("1.9.0", "u")) == current  # the same version
    assert desktop.check_for_update(lambda: ("1.8.5", "u")) == current  # older
    assert desktop.check_for_update(lambda: None) == current  # a release without an installer
    assert watch.UPDATE is None

    def offline():
        raise OSError("no network")
    kind, text = desktop.check_for_update(offline)
    assert kind == "failed" and "no network" in text
    assert watch.UPDATE is None and "no network" in watch.LINES[-1]["text"]
    newer = desktop.check_for_update(lambda: ("1.10.0", "https://github.com/x/BragSetup.exe"))  # 10 > 9, not "1.10" < "1.9"
    assert newer == ("update", "Brag 1.10.0 is out.")
    assert watch.UPDATE == {"version": "1.10.0", "busy": False, "error": ""}
    assert desktop.update_url == "https://github.com/x/BragSetup.exe"
    said = len(watch.LINES)
    assert desktop.check_for_update(lambda: ("1.10.0", "https://github.com/x/BragSetup.exe")) == newer
    assert len(watch.LINES) == said  # told once per version
    assert watch.state(None)["update"]["version"] == "1.10.0"  # the page shows it
    assert watch.state(None)["appVersion"] is None  # set by desktop.main; the command-line companion has none

    # Brag run from source doesn't install BragSetup.exe next to itself
    desktop.install_update()
    assert not watch.UPDATE["busy"] and "git pull" in watch.UPDATE["error"]
    watch.UPDATE["error"] = ""

    # Update: download, start Setup, quit. A failed download keeps Brag running and says so on the page.
    calls = []
    def broken(url, path):
        raise OSError("the download stopped after 5 of 10 bytes")
    watch.UPDATE["busy"] = True
    desktop.update_now(watch.UPDATE, broken, calls.append, lambda: calls.append("quit"))
    assert calls == [] and not watch.UPDATE["busy"] and "5 of 10 bytes" in watch.UPDATE["error"]
    desktop.update_now(watch.UPDATE, lambda url, path: calls.append(url), calls.append, lambda: calls.append("quit"))
    assert calls[0] == "https://github.com/x/BragSetup.exe" and calls[1].endswith("BragSetup-1.10.0.exe")
    assert calls[2] == "quit"
finally:
    desktop.APP_VERSION, watch.UPDATE, desktop.update_url = real_version, None, None
with tempfile.TemporaryDirectory() as d:  # a download that isn't a program is refused, and nothing is left
    path = os.path.join(d, "BragSetup.exe")
    with open(os.path.join(d, "page.html"), "wb") as f:
        f.write(b"<html>rate limited</html>")
    try:
        desktop.download("file:" + urllib.request.pathname2url(os.path.join(d, "page.html")), path)
        assert False, "should refuse"
    except OSError as e:
        assert "isn't a Windows program" in str(e) and os.listdir(d) == ["page.html"]
    with open(os.path.join(d, "setup.exe"), "wb") as f:
        f.write(b"MZ" + b"x" * 1000)
    desktop.download("file:" + urllib.request.pathname2url(os.path.join(d, "setup.exe")), path)
    assert os.path.getsize(path) == 1002

# the installer's pictures: the aspect ratios Inno Setup keeps (brag.iss), at least its recommended sizes
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "windows"))
import installer_art
with tempfile.TemporaryDirectory() as d:
    installer_art.write(d)
    for name, ratio, least in (("wizard-back.png", 497 / 360, 596), ("wizard-image.png", 164 / 314, 202),
                               ("wizard-small.png", 1, 58)):
        with Image.open(os.path.join(d, name)) as img:
            assert abs(img.width / img.height - ratio) < .01 and img.width >= least, (name, img.size)

print("ok")
