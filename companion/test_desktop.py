# Windows only: the tray app's own logic (the window and tray icon themselves are checked by hand).
import os, tempfile
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
    assert desktop.tray_state() == ("idle", "Brag: Choose your WoW folder to get started.")
    watch.GAME_DIR = game
    saved = os.path.join(game, "WTF", "Account", "ME", "SavedVariables")
    os.makedirs(saved)
    with open(os.path.join(saved, "Brag.lua"), "w") as f:
        f.write('BragDB = {\n["webhook"] = "https://discord.com/api/webhooks/1/abc",\n["enabled"] = true,\n}\n')
    assert desktop.tray_state() == ("ok", "Brag: Watching for screenshots.")
    watch.remember(watch.Result("failed", "webhook was deleted (HTTP 404) " + "x" * 200))
    color, tip = desktop.tray_state()
    assert color == "failed" and tip.startswith("Brag: Last post failed: webhook was deleted") and len(tip) == 127
    watch.PAUSED.set()
    assert desktop.tray_state()[0] == "idle"
    watch.PAUSED.clear()
    watch.GAME_DIR, watch.LAST_FAILURE = None, None

# "Start with Windows" runs Brag in the tray, without a console window
assert desktop.launch_command().endswith('desktop.py" --tray') and "pythonw.exe" in desktop.launch_command()
icon = desktop.make_icon(desktop.COLORS["failed"])
assert icon.size == (64, 64) and icon.getpixel((32, 4))[:3] == desktop.COLORS["failed"]

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

print("ok")
