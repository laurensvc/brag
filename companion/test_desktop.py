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

print("ok")
