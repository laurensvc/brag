# Windows only: the tray app's own logic (the window and tray icon themselves are checked by hand).
import os, tempfile
import desktop, watch

with tempfile.TemporaryDirectory() as d:
    game = os.path.join(d, "World of Warcraft", "_forever_")
    os.makedirs(os.path.join(game, "WTF"))
    assert desktop.find_game_dir(game) == game
    assert desktop.find_game_dir(os.path.dirname(game)) == game  # the install folder works too
    assert desktop.find_game_dir(d) is None

    # tray status, most important first
    watch.GAME_DIR = None
    assert desktop.status() == ("idle", "Brag: choose your WoW folder")
    watch.GAME_DIR = game
    assert desktop.status()[1] == "Brag: no Discord webhook yet (/brag in WoW)"
    saved = os.path.join(game, "WTF", "Account", "ME", "SavedVariables")
    os.makedirs(saved)
    with open(os.path.join(saved, "Brag.lua"), "w") as f:
        f.write('BragDB = {\n["webhook"] = "https://discord.com/api/webhooks/1/abc",\n["enabled"] = true,\n}\n')
    assert desktop.status() == ("ok", "Brag: watching for screenshots")
    desktop.last_failure = "webhook was deleted (HTTP 404)"
    assert desktop.status() == ("failed", "Brag: webhook was deleted (HTTP 404)")
    watch.PAUSED.set()
    assert desktop.status() == ("idle", "Brag: paused")
    watch.PAUSED.clear()
    watch.GAME_DIR, desktop.last_failure = None, None

# "Start with Windows" runs Brag in the tray, without a console window
assert desktop.launch_command().endswith('desktop.py" --tray') and "pythonw.exe" in desktop.launch_command()
icon = desktop.make_icon(desktop.COLORS["failed"])
assert icon.size == (64, 64) and icon.getpixel((32, 4))[:3] == desktop.COLORS["failed"]

print("ok")
