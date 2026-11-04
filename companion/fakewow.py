#!/usr/bin/env python3
"""Fake WoW: runs the real Brag addon (Brag/Brag.lua) in Lua 5.1 with a mock WoW API, so you can test the
addon and the companion without the game. Screenshots and SavedVariables land where WoW would put them.

Needs: python3 -m pip install lupa pillow

  python3 companion/fakewow.py DIR --webhook URL    # type the webhook into /brag, Save & reload
  python3 companion/watch.py DIR                    # in another terminal: the real companion
  python3 companion/fakewow.py DIR demo             # play: quest + level up, a legendary, a test post

Events (any number, in order): level, quest=TITLE, loot=ITEM[:QUALITY], print (Print Screen), test (Test post
button), demo. QUALITY is a number 0-6 or a name (default epic); add "uncached" to the loot name's quality, e.g.
loot=Shiny:epic-uncached, to skip the item cache. Each run is one login session: it logs out at the end.
"""
import argparse, datetime, glob, os, sys, time
from PIL import Image, ImageDraw, ImageFont
from lupa.lua51 import LuaRuntime
from watch import CODES

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(HERE, "..", "Brag", "Brag.lua")
QUALITIES = {"poor": 0, "common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5, "artifact": 6}
COLORS = ["9d9d9d", "ffffff", "1eff00", "0070dd", "a335ee", "ff8000", "e6cc80"]


def lua_literal(v, indent=""):
    """Serialize like WoW's SavedVariables writer, which the companion parses."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(v, list):
        return "{\n" + "".join(f"{lua_literal(x)}, -- [{i}]\n" for i, x in enumerate(v, 1)) + "}"
    return "{\n" + "".join(f'["{k}"] = {lua_literal(x)},\n' for k, x in v.items()) + "}"


def to_python(v):
    if hasattr(v, "items"):  # a Lua table: list if keys are 1..n
        d = {k: to_python(x) for k, x in v.items()}
        return [d[i] for i in range(1, len(d) + 1)] if d and set(d) == set(range(1, len(d) + 1)) else d
    return v


class FakeWoW:
    def __init__(self, game_dir, size=(1920, 1080), ui_scale=1.0, jpeg_quality=30, player=None, clock=time.time):
        self.dir, self.size, self.quality, self.clock = game_dir, size, jpeg_quality, clock
        self.shots = os.path.join(game_dir, "Screenshots")
        self.saved = os.path.join(game_dir, "WTF", "Account", "FAKEWOW", "SavedVariables", "Brag.lua")
        os.makedirs(self.shots, exist_ok=True)
        os.makedirs(os.path.dirname(self.saved), exist_ok=True)
        self.player = {"name": "Thrall", "class": "Shaman", "level": 41, "zone": "Orgrimmar", **(player or {})}
        self.ui_scale, self.items, self.taken, self.lua = ui_scale, {}, [], None
        self.login()

    def login(self):
        """Start a session: a fresh Lua state, SavedVariables, then the addon, as WoW does at login or /reload."""
        self.started = self.time() if self.lua else self.clock()
        size = self.size
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        g = self.lua.globals()
        g.HOST = self.lua.table_from({
            "screen": self.lua.table_from({"w": size[0], "h": size[1]}), "uiScale": self.ui_scale,
            "player": self.lua.table_from(self.player), "itemCache": self.lua.table(),
            "screenshot": self._screenshot, "time": self.time,
        })
        with open(os.path.join(HERE, "wowmock.lua"), encoding="utf-8") as f:
            self.lua.execute(f.read())
        if os.path.exists(self.saved):  # WoW runs the SavedVariables file before the addon loads
            with open(self.saved, encoding="utf-8") as f:
                self.lua.execute(f.read())
        with open(ADDON, encoding="utf-8") as f:
            chunk = self.lua.eval("function(src) return assert(loadstring(src, '@Brag.lua')) end")(f.read())
        chunk("Brag")  # an addon file gets the addon name as its first vararg
        self.fire("ADDON_LOADED", "Brag")
        self.fire("PLAYER_ENTERING_WORLD")

    def time(self):
        return self.started + self.lua.globals().MOCK_now()

    def fire(self, event, *args):
        self.lua.globals().MOCK_fire(event, *args)

    def advance(self, seconds):
        self.lua.globals().MOCK_advance(seconds)

    @property
    def db(self):
        return to_python(self.lua.globals().BragDB)

    # --- what a player does ---

    def level_up(self):
        self.player["level"] += 1
        self.fire("PLAYER_LEVEL_UP", self.player["level"])
        self.lua.globals().HOST.player.level = self.player["level"]
        self.advance(5)

    def turn_in(self, title, levels_up=False):
        self.lua.globals().MOCK_questTitle = title
        self.fire("QUEST_COMPLETE")
        self.fire("QUEST_TURNED_IN", 1234, 0, 0)
        if levels_up:  # same moment, like a real turn-in that dings
            self.player["level"] += 1
            self.fire("PLAYER_LEVEL_UP", self.player["level"])
            self.lua.globals().HOST.player.level = self.player["level"]
        self.advance(5)

    def loot(self, name, quality=4, cached=True, pushed=False):
        item_id = 19000 + len(self.items)
        self.items[item_id] = (name, quality)
        if cached:
            self.lua.globals().HOST.itemCache[item_id] = self.lua.table_from({"name": name, "quality": quality})
        link = f"|cff{COLORS[quality]}|Hitem:{item_id}::::::::{self.player['level']}:::::|h[{name}]|h|r"
        fmt = "You receive item: %s." if pushed else "You receive loot: %s."
        self.fire("CHAT_MSG_LOOT", fmt % link, self.player["name"])
        self.advance(5)

    def print_screen(self):
        self._screenshot()
        self.fire("SCREENSHOT_SUCCEEDED")
        self.advance(1)

    def slash(self):
        self.lua.globals().SlashCmdList.BRAG("")

    def click(self, label):
        button = self.lua.globals().MOCK_find("Button", label)
        assert button, f"no visible button {label!r}"
        button.Click(button)
        if self.lua.globals().MOCK_reloaded:  # Save & reload
            self.logout()
            self.login()
        self.advance(5)

    def type_webhook(self, url):
        box = self.lua.globals().MOCK_find("EditBox")
        assert box, "open /brag first"
        box.SetText(box, url)

    def logout(self):
        """Write SavedVariables, as WoW does on logout or /reload."""
        g = self.lua.globals()
        with open(self.saved, "w", encoding="utf-8") as f:
            f.write(f"\nBragDB = {lua_literal(to_python(g.BragDB))}\nBragHistory = {lua_literal(to_python(g.BragHistory) or [])}\n")

    # --- the screenshot WoW would take ---

    def _screenshot(self):
        w, h = self.size
        sky = Image.linear_gradient("L").resize((w, h))
        img = Image.merge("RGB", (sky.point(lambda v: 40 + v // 3), sky.point(lambda v: 70 + v // 3), sky.point(lambda v: 120 + v // 4)))
        img = Image.blend(img, Image.effect_noise((w, h), 60).convert("RGB"), 0.25)  # texture, so JPEG behaves like a game frame
        d = ImageDraw.Draw(img)
        d.rectangle([0, int(h * 0.62), w, h], fill=(52, 70, 38))
        g = self.lua.globals()
        banners = [g.MOCK_banners[i] for i in range(1, len(g.MOCK_banners) + 1)]
        banners = [CODES.sub("", b.text) for b in banners if g.MOCK_now() - b.at < 10][-2:]  # raid warnings last ~10 s
        try:
            font = ImageFont.load_default(size=max(16, h // 24))
        except (TypeError, OSError):  # old Pillow without sizes
            font = ImageFont.load_default()
        for i, text in enumerate(reversed(banners)):
            d.text((w / 2, h * 0.22 + i * h / 18), text, font=font, fill=(255, 72, 0), anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
        rects = g.MOCK_render()
        for x, y, bw, bh, r, gr, b, _ in (tuple(rects[i][k] for k in range(1, 9)) for i in range(1, len(rects) + 1)):
            d.rectangle([round(x), round(y), round(x + bw) - 1, round(y + bh) - 1], fill=(round(r * 255), round(gr * 255), round(b * 255)))
        stamp = datetime.datetime.fromtimestamp(self.time())
        path = os.path.join(self.shots, stamp.strftime("WoWScrnShot_%m%d%y_%H%M%S.jpg"))
        while os.path.exists(path):  # several in one second: WoW would wait a frame; keep them apart
            stamp += datetime.timedelta(seconds=1)
            path = os.path.join(self.shots, stamp.strftime("WoWScrnShot_%m%d%y_%H%M%S.jpg"))
        img.save(path, "JPEG", quality=self.quality)
        self.taken.append(path)


def run(wow, event):
    kind, _, arg = event.partition("=")
    if kind == "level":
        wow.level_up()
    elif kind == "quest":
        wow.turn_in(arg or "The Defias Brotherhood")
    elif kind == "loot":
        name, _, quality = arg.rpartition(":") if ":" in arg else (arg, "", "epic")
        quality, cached = quality.removesuffix("-uncached"), not quality.endswith("-uncached")
        wow.loot(name or "Thunderfury, Blessed Blade of the Windseeker", int(quality) if quality.isdigit() else QUALITIES[quality], cached)
    elif kind == "print":
        wow.print_screen()
    elif kind == "test":
        wow.slash()
        wow.click("Test post")
    elif kind == "demo":
        wow.turn_in("Bounty on Murlocs", levels_up=True)
        wow.loot("Thunderfury, Blessed Blade of the Windseeker", 5)
        wow.slash()
        wow.click("Test post")
    else:
        sys.exit(f"Unknown event {event!r}. See --help.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("game_dir")
    p.add_argument("events", nargs="*")
    p.add_argument("--webhook", help="type this into /brag and click Save & reload")
    p.add_argument("--size", default="1920x1080", help="screen size, e.g. 2560x1440")
    p.add_argument("--ui-scale", type=float, default=1.0)
    p.add_argument("--jpeg", type=int, default=30, help="screenshot JPEG quality (WoW's default 3 is roughly 30)")
    p.add_argument("--name", default="Thrall")
    p.add_argument("--zone", default="Orgrimmar")
    a = p.parse_args()
    w, h = map(int, a.size.lower().split("x"))
    wow = FakeWoW(a.game_dir, (w, h), a.ui_scale, a.jpeg, {"name": a.name, "zone": a.zone})
    if a.webhook:
        wow.slash()
        wow.type_webhook(a.webhook)
        wow.click("Save & reload")
        print(f"Webhook saved. Settings: {wow.saved}")
    for event in a.events:
        run(wow, event)
    wow.logout()
    for path in wow.taken:
        print("screenshot:", path)
    if not glob.glob(os.path.join(a.game_dir, "Screenshots", "*")) and not a.webhook:
        print("No screenshots taken: is Brag enabled, and the event turned on? (see", wow.saved + ")")


if __name__ == "__main__":
    main()
