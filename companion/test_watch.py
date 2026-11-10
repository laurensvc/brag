import io, json, os, random, subprocess, tempfile, threading, time, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageDraw
import watch
from watch import (CODES, COMPANION_DEFAULTS, DEFAULTS, MAX_BYTES, WEBHOOK, caption, cleanup, fletcher, parse_saved,
                   post, prepare, read_strip, save_settings, validate, validate_companion)

HOOK = "https://discord.com/api/webhooks/123/abc-DEF_9"
# Shaped like the file WoW writes on logout
SAVED = f'''
BragDB = {{
["webhook"] = "{HOOK}",
["enabled"] = false,
["minQuality"] = 4,
}}
BragHistory = {{
{{
["time"] = 1762270000,
["text"] = "Quest complete: The \\"Defias\\" Brotherhood",
}}, -- [1]
{{
["text"] = "Big drop: |cffa335ee|Hitem:19019::::::::60:::::|h[Thunderfury]|h|r",
["time"] = 1762270100,
}}, -- [2]
}}
'''

db, history = parse_saved(SAVED)
assert db == {"webhook": HOOK, "enabled": False, "minQuality": 4}, db
assert history[0] == {"time": 1762270000, "text": 'Quest complete: The "Defias" Brotherhood'}, history
assert CODES.sub("", history[1]["text"]) == "Big drop: [Thunderfury]"
assert parse_saved("") == ({}, [])

# webhook check: only real Discord webhooks, nothing curl could read as an option
assert WEBHOOK.match(HOOK) and WEBHOOK.match("https://ptb.discord.com/api/webhooks/1/x")
for bad in ["https://evil.example/api/webhooks/1/x", "https://evildiscord.com/api/webhooks/1/x",
            "-o /tmp/x https://discord.com/api/webhooks/1/x", 'https://discord.com/api/webhooks/1/x"']:
    assert not WEBHOOK.match(bad), bad

assert validate(dict(DEFAULTS)) is None
assert validate({**DEFAULTS, "webhook": "https://evil.example/x"})
assert validate({**DEFAULTS, "minQuality": 9})
assert validate({**DEFAULTS, "enabled": "yes"})
assert validate({**DEFAULTS, "extra": 1})
assert validate(None)

assert validate_companion(dict(COMPANION_DEFAULTS)) is None
for bad in [{"retries": 4}, {"retries": True}, {"maxHeight": 1000}, {"jpegQuality": 99}, {"keepDays": 0},
            {"caption": 1}, {"extra": 1}]:
    assert validate_companion({**COMPANION_DEFAULTS, **bad}), bad
assert validate_companion(None)

# saving rewrites BragDB but keeps the history and unknown keys intact
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "Brag.lua")
    with open(path, "w") as f:
        f.write(SAVED.replace('["minQuality"] = 4,', '["minQuality"] = 4,\n["future"] = "x",'))
    save_settings(path, {**DEFAULTS, "minQuality": 3})
    db2, history2 = parse_saved(open(path).read())
    assert db2 == {**DEFAULTS, "minQuality": 3, "future": "x"}, db2
    assert history2 == history


# --- data strip: a Python copy of drawStrip in Brag.lua ---

def draw_strip(img, payload, block=8):
    data = payload.encode()
    per_row = img.width // block
    bits = "".join(f"{b:08b}" for b in bytes([66, 103, per_row >> 8, per_row & 255, len(data)]) + data + fletcher(data))
    d = ImageDraw.Draw(img)
    for n, bit in enumerate(bits):
        x, y = n % per_row * block, n // per_row * block
        d.rectangle([x, y, x + block - 1, y + block - 1], fill=(255, 255, 255) if bit == "1" else (0, 0, 0))
    return img


def noisy(w, h):
    rnd = random.Random(1)
    return Image.frombytes("RGB", (w, h), rnd.randbytes(w * h * 3))


def jpeg(img, quality):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return Image.open(buf)


LOOT = "1\tloot\tThrall\tShaman\t60\tMolten Core\tThunderfury, Blessed Blade of the Windseeker\t5"
QUEST = "1\tquest\tJaïna_*\tMage\t12\tWestfall\tThe [Defias] Brotherhood @everyone\t"
for payload, size, quality, scale in [(LOOT, (1920, 1080), 25, 1), (QUEST, (1280, 720), 15, 1),
                                      (LOOT, (1280, 720), 50, 1.5), ("x" * 250, (1024, 768), 25, 1)]:
    img = draw_strip(noisy(*size), payload)
    if scale != 1:  # e.g. a screenshot taken at a different render scale
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.NEAREST)
    text, crop = read_strip(jpeg(img, quality))
    assert text == payload, (text, payload)
    assert 8 * scale <= crop <= 8 * scale * 22, crop  # crop removes the strip rows, nothing much more
assert read_strip(jpeg(noisy(800, 600), 25)) == (None, 0)  # a screenshot the player took themselves

assert caption(LOOT) == ("💎 **Thrall** looted **\\[Thunderfury, Blessed Blade of the Windseeker\\]** (Legendary)"
                         "\n-# Level 60 Shaman · Molten Core"), caption(LOOT)
assert caption(LOOT, md=False) == ("💎 Thrall looted [Thunderfury, Blessed Blade of the Windseeker] (Legendary)"
                                   " · Level 60 Shaman · Molten Core")
assert caption(QUEST).startswith("📜 **Jaïna\\_\\*** completed **The \\[Defias\\] Brotherhood @everyone**")
assert caption("1\tlevel\tThrall\tShaman\t42\tOrgrimmar\t\t") == "🎉 **Thrall** reached **level 42**!\n-# Shaman · Orgrimmar"
assert caption("1\tlevel\tThrall\t\t42\t\t\t") == "🎉 **Thrall** reached **level 42**!"
assert caption("1\tboss\tThrall\tShaman\t60\tMolten Core\tMajordomo *Executus*\t") == (
    "⚔️ **Thrall** defeated **Majordomo \\*Executus\\***!\n-# Level 60 Shaman · Molten Core")
assert caption("1\tdeath\tThrall\tShaman\t60\tMolten Core\t\t", md=False) == "💀 Thrall died · Level 60 Shaman · Molten Core"
assert caption("1\tdeath\tThrall\tShaman\t60\tMolten Core\tRagnaros's Lava_Burst\t") == (
    "💀 **Thrall** died to **Ragnaros's Lava\\_Burst**\n-# Level 60 Shaman · Molten Core")
assert validate({**DEFAULTS, "death": "no"}) and validate({k: v for k, v in DEFAULTS.items() if k != "boss"})
assert caption("2\tfuture\tformat") == caption(None) == caption("1\tdance\ta\tb\tc\td\te\tf") == ""

# the 9th field: numbers for the caption. Level-ups and finished dungeons get them on a line of their own
assert watch.numbers("bosses=3,time=-1,x=,=4,junk,y=1.5") == {"bosses": 3, "time": -1}
assert [watch.duration(s) for s in (0, 59, 61, 3600, 7500, 86400 + 5 * 3600 + 59)] == ["1m", "1m", "1m", "1h 00m", "2h 05m", "1d 5h"]
assert caption("1\tlevel\tThrall\tShaman\t42\tOrgrimmar\t\t\tdeaths=0,played=138000,took=7500") == (
    "🎉 **Thrall** reached **level 42**!\n⏱️ Level 41 took 2h 05m · no deaths · 1d 14h played\n-# Shaman · Orgrimmar")
assert caption("1\tlevel\tThrall\tShaman\t42\tOrgrimmar\t\t\tdeaths=2", md=False) == (
    "🎉 Thrall reached level 42! · ⏱️ 2 deaths · Shaman · Orgrimmar")
assert caption("1\trun\tThrall\tShaman\t30\tThe Barrens\tWailing *Caverns*\t\tbosses=8,deaths=4,raid=0,time=4320,wipes=1") == (
    "🏰 **Thrall** finished **Wailing \\*Caverns\\***!\n⚔️ 8 bosses · 1 wipe · 4 deaths · 1h 12m\n-# Level 30 Shaman · The Barrens")
assert caption("1\trun\tThrall\tShaman\t60\t\tMolten Core\t\tbosses=1,deaths=0,raid=1,time=0", md=False) == (
    "🐉 Thrall finished the raid Molten Core! · ⚔️ 1 boss · no deaths · Level 60 Shaman")
# a big drop links to the item on Wowhead (on the page: just the name)
assert caption(LOOT + "\titem=19019").startswith(
    "💎 **Thrall** looted [**Thunderfury, Blessed Blade of the Windseeker**](<https://www.wowhead.com/forever/item=19019>) (Legendary)\n")
assert caption(LOOT + "\titem=19019", md=False) == caption(LOOT, md=False)

# funny captions: every line fills in for its event, with names escaped; the post and the page get the same line
import flavor
events = {"level": "1\tlevel\tPi*erre\tMage\t10\t\t\t", "quest": QUEST, "loot": LOOT,
          "boss": "1\tboss\tThrall\tShaman\t60\tMolten Core\tRagnaros\t", "death": "1\tdeath\tThrall\tShaman\t60\t\t\t",
          "run": "1\trun\tThrall\tShaman\t60\tBurning Steppes\tBlackrock Depths\t\tbosses=3",
          "death_by": "1\tdeath\tThrall\tShaman\t60\t\tHogger\t"}
assert set(flavor.FLAVOR) == set(events) and all(len(lines) >= 10 for lines in flavor.FLAVOR.values())
for kind, lines in flavor.FLAVOR.items():
    for line in lines:
        assert not watch.MARKDOWN.search(line.replace("{", "").replace("}", "")), line  # plain text, see flavor.py
        line.format(who="", level="", quest="", item="", boss="", instance="", killer="", zone="")  # no unknown placeholders
    assert len(set(lines)) == len(lines), kind  # no line twice
    seen = {caption(events[kind], md=False, funny=True, seed=str(i)) for i in range(2000)}
    assert len(seen) == len(lines), (kind, len(seen))  # every line comes up
for i in range(40):
    md, plain = caption(LOOT, funny=True, seed=str(i)), caption(LOOT, md=False, funny=True, seed=str(i))
    assert md.replace("**", "").replace("\\", "") == plain.replace(" · ", "\n-# ", 1), (md, plain)
    assert "(Legendary)" in plain and "-# Level 60 Shaman · Molten Core" in md
assert all("Pi\\*erre" in caption(events["level"], funny=True, seed=str(i)) for i in range(40))
assert caption(events["death"], md=False, funny=True, seed="x") == caption(events["death"], md=False, funny=True, seed="x")
assert caption(LOOT, funny=False) == caption(LOOT)  # switched off: the plain line


# --- image prep and posting ---

with tempfile.TemporaryDirectory() as d:
    out = os.path.join(d, "a.jpg")
    prepare(noisy(3840, 2160), COMPANION_DEFAULTS, out)
    assert Image.open(out).size == (1920, 1080)
    prepare(noisy(1280, 720), {**COMPANION_DEFAULTS, "maxHeight": 1080}, out)
    assert Image.open(out).size == (1280, 720)
    prepare(noisy(3840, 2160), {**COMPANION_DEFAULTS, "maxHeight": 0, "jpegQuality": 95}, out)
    assert Image.open(out).size == (3840, 2160) and os.path.getsize(out) <= MAX_BYTES  # quality drops until it fits


def fake_curl(*responses):
    calls, sleeps = [], []
    def run(cmd, **kw):
        calls.append(cmd)
        code, body = responses[len(calls) - 1]
        return subprocess.CompletedProcess(cmd, 0 if code else 7, f"{body}\n{code:03d}", "" if code else "curl: (7) Failed to connect")
    return run, calls, sleeps


run, calls, sleeps = fake_curl((429, '{"retry_after": 1.5}'), (200, "{}"))
assert str(post("x.jpg", "hi", HOOK, 3, run, sleeps.append)) == "posted after 1 retry" and sleeps == [1.5]
run, calls, sleeps = fake_curl(*[(502, "")] * 4)
assert post("x.jpg", "hi", HOOK, 3, run, sleeps.append) == watch.Result("failed", "Discord had a problem (HTTP 502) after 3 retries")
assert sleeps == [2, 4, 8] and len(calls) == 4
run, calls, sleeps = fake_curl((0, ""), (204, ""))
assert post("x.jpg", "hi", HOOK, 1, run, sleeps.append) == watch.Result("posted", "after 1 retry")
run, calls, sleeps = fake_curl((404, '{"message": "Unknown Webhook"}'))
assert str(post("x.jpg", "hi", HOOK, 3, run, sleeps.append)) == "failed: webhook was deleted (HTTP 404)" and not sleeps
run, calls, sleeps = fake_curl((0, ""))
assert str(post("x.jpg", "hi", HOOK, 0, run, sleeps.append)) == "failed: curl: (7) Failed to connect" and len(calls) == 1

# real curl against a local server: the caption (emoji, accents) and the file arrive intact
received = {}
class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_POST(self):
        received["body"] = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.end_headers()
server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory() as d:
    shot = os.path.join(d, "WoWScrnShot_110426_201500.jpg")
    noisy(64, 64).save(shot)
    status = post(shot, caption(QUEST), f"http://127.0.0.1:{server.server_port}/hook", 0)
server.shutdown()
assert status == watch.Result("posted"), status
body = received["body"]
sent = json.loads(body.split(b'name="payload_json"')[1].split(b"\r\n\r\n", 1)[1].split(b"\r\n--")[0])
assert sent == {"content": caption(QUEST), "allowed_mentions": {"parse": []}}, sent
assert b'filename="WoWScrnShot_110426_201500.jpg"' in body and b"\xff\xd8" in body
# the webhook test: just the text, no file
server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
status = post(None, watch.TEST_TEXT, f"http://127.0.0.1:{server.server_port}/hook", 0)
server.shutdown()
assert status == watch.Result("posted"), status
assert b"filename=" not in received["body"] and "Brag test".encode() in received["body"]


# --- the whole flow for one screenshot, and cleanup ---

with tempfile.TemporaryDirectory() as game:
    os.makedirs(os.path.join(game, "Screenshots"))
    os.makedirs(os.path.join(game, "WTF", "Account", "ME", "SavedVariables"))
    with open(os.path.join(game, "WTF", "Account", "ME", "SavedVariables", "Brag.lua"), "w") as f:
        f.write(SAVED.replace("false", "true"))
    shot = os.path.join(game, "Screenshots", "WoWScrnShot_1.jpg")
    jpeg(draw_strip(noisy(1920, 1080), LOOT), 30).save(shot)
    watch.LOG, watch.CONFIG = os.path.join(game, "log.jsonl"), os.path.join(game, "cfg.json")
    posted = []
    real_post, watch.post = watch.post, lambda path, text, hook, retries: posted.append((Image.open(path).copy(), text, hook, retries)) or watch.Result("posted")
    status, text = watch.handle(game, "WoWScrnShot_1.jpg")
    watch.post = real_post
    img, sent, hook, retries = posted[0]
    funny = lambda md: caption(LOOT, md=md, funny=True, seed="WoWScrnShot_1.jpg")  # the default: a joke line
    assert (status, text, sent, hook, retries) == (watch.Result("posted"), funny(False), funny(True), HOOK, 3)
    assert "[Thunderfury, Blessed Blade of the Windseeker] (Legendary)" in text  # the page still colors the item
    assert img.width == 1920 and 1000 < img.height < 1080 and read_strip(img) == (None, 0)  # strip cropped off

    with open(watch.CONFIG, "w") as f:
        f.write("{not json")
    assert watch.load_companion() == COMPANION_DEFAULTS
    watch.save_companion({**COMPANION_DEFAULTS, "retries": 1})
    assert watch.load_companion()["retries"] == 1

    now = time.time()
    with open(watch.LOG, "w") as f:
        for name, age in [("old", 8), ("new", 1)]:
            f.write(json.dumps({"name": name, "status": "posted", "time": now - age * 86400}) + "\n")
        f.write("garbage\nnull\n42\n")  # not entries: skipped, never fatal
    old = os.path.join(game, "Screenshots", "old.jpg")
    noisy(8, 8).save(old)
    os.utime(old, (now - 8 * 86400, now - 8 * 86400))
    assert cleanup(game, COMPANION_DEFAULTS, now) == 0 and os.path.exists(old)  # screenshots kept by default
    assert list(watch.statuses()) == ["new"] and watch.statuses()["new"]["kind"] == "posted"  # an older entry
    assert cleanup(game, {**COMPANION_DEFAULTS, "deleteShots": True}, now) == 1
    assert sorted(os.listdir(os.path.join(game, "Screenshots"))) == ["WoWScrnShot_1.jpg"]

assert watch.open_when_ready("missing.jpg", timeout=1, sleep=lambda s: None) is None


# --- the watcher: pausing, switching WoW folders, telling listeners ---

with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
    watch.LOG, watch.CONFIG = os.path.join(a, "log.jsonl"), os.path.join(a, "cfg.json")
    watch.TEXT_LOG = os.path.join(a, "brag.log")  # like the desktop app: tracebacks go here, not the console
    results, handled = [], []
    real_handle, watch.handle = watch.handle, lambda game, name: handled.append((game, name)) or (watch.Result("posted"), "cap")
    watch.LISTENERS.append(lambda *r: results.append(r))
    try:
        watch.GAME_DIR = None
        assert watch.watch_once(watch.Watching()) == watch.Watching()
        state = watch.state(None)  # no folder yet: the page still loads
        assert state["gameDir"] == "" and state["shots"] == [] and not state["found"]

        watch.GAME_DIR = a
        noisy(8, 8).save(os.path.join(a, "before.jpg"))  # not in Screenshots: ignored
        w = watch.watch_once(watch.Watching())
        assert w.folder == os.path.join(a, "Screenshots") and os.path.isdir(w.folder)  # created for WoW
        noisy(8, 8).save(os.path.join(w.folder, "one.jpg"))
        with open(os.path.join(w.folder, "notes.txt"), "w") as f:
            f.write("x")
        w = watch.watch_once(w)
        assert handled == [(a, "one.jpg")] and results == [("one.jpg", watch.Result("posted"), "cap")]

        watch.PAUSED.set()
        noisy(8, 8).save(os.path.join(w.folder, "two.jpg"))
        w = watch.watch_once(w)
        watch.PAUSED.clear()
        w = watch.watch_once(w)  # skipped while paused, and not posted after resuming
        assert len(handled) == 1 and results[-1] == ("two.jpg", watch.Result("skipped", "paused"), "")
        assert watch.statuses()["two.jpg"]["status"] == "skipped: paused" and watch.statuses()["two.jpg"]["kind"] == "skipped"
        assert watch.LINES[-1]["kind"] == "skipped"

        os.makedirs(os.path.join(b, "Screenshots"))
        noisy(8, 8).save(os.path.join(b, "Screenshots", "old.jpg"))  # already there when we switch: not posted
        watch.GAME_DIR = b
        w = watch.watch_once(w)
        noisy(8, 8).save(os.path.join(b, "Screenshots", "new.jpg"))
        w = watch.watch_once(w)
        assert handled[1:] == [(b, "new.jpg")]
        assert any("Watching" in line["text"] and b in line["text"] for line in watch.LINES)
        assert watch.state(b)["log"][0]["text"] == "posted: new.jpg (cap)"  # newest first

        # a broken listener doesn't stop the other listeners, and the error is in the log
        def broken(*r):
            raise RuntimeError("tray went away")
        watch.LISTENERS.insert(0, broken)
        noisy(8, 8).save(os.path.join(b, "Screenshots", "after.jpg"))
        w = watch.watch_once(w)
        assert handled[-1] == (b, "after.jpg") and results[-1][0] == "after.jpg"
        assert any("broken failed: RuntimeError: tray went away" in line["text"] for line in watch.LINES)
        assert watch.LAST_FAILURE == "broken failed: tray went away"
        watch.LISTENERS.remove(broken)

        # any error in a pass is reported once (log + listeners), and the next pass carries on
        real_dir, watch.screenshots_dir = watch.screenshots_dir, lambda game: 1 / 0
        try:
            w, error = watch.guarded_pass(w, None)
            assert error and results[-1] == ("Brag", watch.Result("failed", "watcher error: division by zero"), "")
            assert watch.LAST_FAILURE == "watcher error: division by zero"  # the tray turns red
            n = len(results)
            w, error = watch.guarded_pass(w, error)  # same error again: not reported again
            assert len(results) == n
        finally:
            watch.screenshots_dir = real_dir
        noisy(8, 8).save(os.path.join(b, "Screenshots", "later.jpg"))
        w, error = watch.guarded_pass(w, error)
        assert error is None and handled[-1] == (b, "later.jpg")

        # a cleanup that keeps failing is retried hourly, not every pass, so posting goes on
        real_cleanup, watch.cleanup = watch.cleanup, lambda *a: 1 / 0
        try:
            w.cleaned = 0
            noisy(8, 8).save(os.path.join(b, "Screenshots", "during.jpg"))
            w, error = watch.guarded_pass(w, None)
            assert error is None and handled[-1] == (b, "during.jpg") and w.cleaned > 0
        finally:
            watch.cleanup = real_cleanup

        # the Screenshots folder going away: reported (tray red), then screenshots taken meanwhile get posted
        real_listdir = os.listdir
        def gone(path="."):
            if "Screenshots" in str(path):
                raise FileNotFoundError(2, "The system cannot find the path specified", str(path))
            return real_listdir(path)
        os.listdir = gone
        try:
            w, error = watch.guarded_pass(w, None)
            assert error and watch.LAST_FAILURE.startswith("can't read the Screenshots folder")
        finally:
            os.listdir = real_listdir
        noisy(8, 8).save(os.path.join(b, "Screenshots", "meanwhile.jpg"))
        w, error = watch.guarded_pass(w, error)
        assert error is None and handled[-1] == (b, "meanwhile.jpg")
        with open(watch.TEXT_LOG, encoding="utf-8") as f:
            detail = f.read()
        assert "Traceback" in detail and "ZeroDivisionError" in detail and "tray went away" in detail
        assert watch.LAST_FAILURE is None  # a post worked again

        # switching the WoW folder mid-pass: this pass finishes in the old folder, the next one moves
        for n in ("x1.jpg", "x2.jpg"):
            noisy(8, 8).save(os.path.join(b, "Screenshots", n))
        def switch(game, name):
            watch.GAME_DIR = a
            handled.append((game, name))
            return watch.Result("posted"), ""
        watch.handle = switch
        w = watch.watch_once(w)
        assert handled[-2:] == [(b, "x1.jpg"), (b, "x2.jpg")] and results[-1][1].kind == "posted"
        w = watch.watch_once(w)
        assert w.folder == os.path.join(a, "Screenshots")
    finally:
        watch.handle, watch.GAME_DIR, watch.TEXT_LOG = real_handle, None, None
        watch.LISTENERS.clear()

# the page server: a second Brag asks the first to show its window; other sites can't
shown = []
watch.ON_SHOW = lambda: shown.append(1)
server = watch.Server(("127.0.0.1", 0), watch.Handler)
port = server.server_port
threading.Thread(target=server.serve_forever, daemon=True).start()
watch.ORIGINS = {f"http://127.0.0.1:{port}"}

def call(path, origin, data=b"{}"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers={"Origin": origin})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

assert call("/api/show", f"http://127.0.0.1:{port}") == (200, {}) and shown == [1]
assert call("/api/show", "https://evil.example")[0] == 403 and shown == [1]
assert call("/api/settings", f"http://127.0.0.1:{port}", json.dumps(DEFAULTS).encode()) == (400, {"error": "Choose your WoW folder first."})
with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state") as r:
    st = json.loads(r.read())
    assert st["gameDir"] == "" and st["canChooseFolder"] is False
# choosing the WoW folder from the page: only when the desktop app answers it
me = f"http://127.0.0.1:{port}"
assert call("/api/folder", me, b'{"path": "C:/x"}')[0] == 404
watch.ON_FOLDER = lambda path: None if path == "C:/wow" else "That isn't a WoW folder."
assert call("/api/folder", me, b'{"path": "C:/x"}') == (400, {"error": "That isn't a WoW folder."})
assert call("/api/folder", me, b'{"path": " "}')[0] == 400
assert call("/api/folder", me, b'{"path": "C:/wow"}')[0] == 200
assert call("/api/folder", "https://evil.example", b'{"path": "C:/wow"}')[0] == 403
watch.ON_FOLDER = None
# Send test message: checks the URL in the field (no WoW folder or settings file needed) and reports what Discord said
real_post, posted = watch.post, []
watch.post = lambda path, text, hook, retries: posted.append((path, hook, retries)) or watch.Result("failed", "webhook was deleted (HTTP 404)")
try:
    assert call("/api/test", me, b'{"webhook": " "}') == (400, {"error": "Paste your Discord webhook URL first."})
    assert call("/api/test", me, b'{"webhook": "https://evil.example/x"}') == (400, {"error": "That isn't a Discord webhook URL"})
    assert call("/api/test", me, b"nope")[0] == 400 and posted == []
    assert call("/api/test", me, json.dumps({"webhook": f" {HOOK} "}).encode()) == (200, {"kind": "failed", "reason": "webhook was deleted (HTTP 404)"})
    assert posted == [(None, HOOK, 0)] and watch.LINES[-1]["text"] == "Test message failed: webhook was deleted (HTTP 404)"
    watch.post = lambda *a: watch.Result("posted")
    assert call("/api/test", me, json.dumps({"webhook": HOOK}).encode()) == (200, {"kind": "posted", "reason": ""})
    assert call("/api/test", "https://evil.example", json.dumps({"webhook": HOOK}).encode())[0] == 403
finally:
    watch.post = real_post

# the Discord link is kept by the app; the Advanced form leaves it out and keeps it; the addon can be (re)installed
with tempfile.TemporaryDirectory() as game:
    watch.CONFIG = os.path.join(game, "cfg.json")
    post_json = lambda path, data: call(path, me, json.dumps(data).encode())
    assert post_json("/api/webhook", {"webhook": "https://evil.example/x"})[0] == 400
    assert post_json("/api/webhook", {"webhook": f" {HOOK} "}) == (200, {}) and watch.load_companion()["webhook"] == HOOK
    assert post_json("/api/companion", {**COMPANION_DEFAULTS, "retries": 1} | {"webhook": HOOK})[0] == 200
    cfg = {k: v for k, v in COMPANION_DEFAULTS.items() if k != "webhook"}
    assert post_json("/api/companion", {**cfg, "retries": 2})[0] == 200
    assert watch.load_companion()["retries"] == 2 and watch.load_companion()["webhook"] == HOOK
    assert post_json("/api/companion", {**cfg, "extra": 1})[0] == 400
    assert post_json("/api/webhook", {"webhook": ""}) == (200, {}) and watch.load_companion()["webhook"] == ""
    assert post_json("/api/addon", {}) == (400, {"error": "Choose your WoW folder first."})
    watch.GAME_DIR = game
    assert post_json("/api/addon", {}) == (200, {"version": watch.addon_version(watch.ADDON)})
    watch.GAME_DIR = None
assert watch.webhook_for({"webhook": "in game"}, {"webhook": "app"}) == "app"
assert watch.webhook_for({"webhook": "in game"}, {"webhook": ""}) == "in game" and watch.webhook_for({}, {"webhook": ""}) == ""
assert validate({k: v for k, v in DEFAULTS.items() if k != "webhook"}) is None  # the page no longer sends it
# the page's textures and font are served; nothing else from the folder is
with urllib.request.urlopen(f"http://127.0.0.1:{port}/assets/Cinzel.ttf") as r:
    assert r.headers["Content-Type"] == "font/ttf"
for bad in ["/assets/CREDITS.md", "/assets/../watch.py", "/assets/..%2Fwatch.py"]:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}{bad}")
        raise AssertionError(bad)
    except urllib.error.HTTPError as e:
        assert e.code == 404, (bad, e.code)
server.shutdown()

# results written by an older Brag still read right
R = watch.Result
assert R.from_text("posted") == R("posted") and R.from_text("posted after 2 retries") == R("posted", "after 2 retries")
assert R.from_text("failed: webhook was deleted (HTTP 404)") == R("failed", "webhook was deleted (HTTP 404)")
assert R.from_text("skipped: paused") == R("skipped", "paused") and R.from_text("").kind == "skipped"
assert str(R("posted")) == "posted" and str(R("skipped", "paused")) == "skipped: paused"

# the addon: installed when Brag first looks at a WoW folder, updated when Brag carries a newer one, a newer one kept
with tempfile.TemporaryDirectory() as game:
    target = watch.addon_dir(game)
    ours = watch.addon_version(watch.ADDON)
    assert ours and watch.addon_status(game) == ("missing", None)
    watch.GAME_DIR = game
    watch.watch_once(watch.Watching())
    assert watch.addon_status(game) == ("ok", ours)
    for name in ("Brag.lua", "Brag.toc", "icon.tga"):
        with open(os.path.join(watch.ADDON, name), "rb") as a, open(os.path.join(target, name), "rb") as b:
            assert a.read() == b.read()
    with open(os.path.join(target, "Brag.toc"), "w") as f:
        f.write("## Interface: 11507\n## Version: 0.1\n")
    assert watch.addon_status(game) == ("outdated", "0.1")
    watch.ensure_addon(game)
    assert watch.addon_status(game) == ("ok", ours) and "/reload" in watch.LINES[-1]["text"]
    with open(os.path.join(target, "Brag.toc"), "w") as f:
        f.write("## Version: 99.0\n")  # from CurseForge, newer than this Brag's
    watch.ensure_addon(game)
    assert watch.addon_status(game) == ("ok", "99.0")
    watch.GAME_DIR = None
with tempfile.TemporaryDirectory() as game:
    os.makedirs(os.path.join(game, "Interface"))
    with open(os.path.join(game, "Interface", "AddOns"), "w") as f:
        f.write("not a folder")  # can't install here: reported, not raised
    watch.ensure_addon(game)
    assert watch.addon_status(game)[0] == "missing" and "Couldn't install" in watch.LINES[-1]["text"]

# one status for the tray and the page, the most important first
with tempfile.TemporaryDirectory() as game:
    watch.CONFIG = os.path.join(game, "cfg.json")
    watch.GAME_DIR, watch.LAST_FAILURE = None, None
    assert watch.status()[0] == "setup" and "WoW folder" in watch.status()[1]
    watch.GAME_DIR = game
    assert watch.status()[0] == "setup" and "addon isn't in WoW yet" in watch.status()[1]
    steps = watch.state(game)["setup"]
    assert steps["folder"] and steps["addon"] == "missing" and steps["canInstall"] and not steps["webhook"] and not steps["played"]
    watch.install_addon(game)
    assert watch.status()[0] == "setup" and "Discord link" in watch.status()[1]  # no WoW login needed any more
    watch.save_companion({**watch.load_companion(), "webhook": HOOK})  # the app's link is enough to post
    assert watch.status()[0] == "ok"
    watch.save_companion({**watch.load_companion(), "webhook": ""})
    saved = os.path.join(game, "WTF", "Account", "ME", "SavedVariables")
    os.makedirs(saved)
    with open(os.path.join(saved, "Brag.lua"), "w") as f:
        f.write('BragDB = {\n["enabled"] = false,\n}\n')
    assert watch.status()[0] == "setup" and "Discord link" in watch.status()[1]
    with open(os.path.join(saved, "Brag.lua"), "w") as f:
        f.write(f'BragDB = {{\n["webhook"] = "{HOOK}",\n["enabled"] = false,\n}}\n')  # the link from /brag works too
    assert watch.status()[0] == "off"
    with open(os.path.join(saved, "Brag.lua"), "w") as f:
        f.write(f'BragDB = {{\n["webhook"] = "{HOOK}",\n["enabled"] = true,\n}}\n')
    assert watch.status() == ("ok", "Ready. Play WoW: your big moments get posted to Discord.")
    steps = watch.state(game)["setup"]
    assert steps["addon"] == "ok" and steps["webhook"] and steps["played"]  # the settings file: WoW ran Brag
    watch.remember(R("failed", "webhook was deleted (HTTP 404)"))
    assert watch.status() == ("failed", "Last post failed: webhook was deleted (HTTP 404)")
    watch.PAUSED.set()
    assert watch.status()[0] == "paused"  # pausing outranks the last failure
    watch.PAUSED.clear()
    assert watch.state(game)["status"]["kind"] == "failed"  # the page gets the same
    watch.remember(R("posted"))
    assert watch.status()[0] == "ok"
    watch.GAME_DIR = None


# the companion tells the addon it runs (BragDB.companion), so the addon stops asking to install the app
with tempfile.TemporaryDirectory() as game:
    acc = lambda name: os.path.join(game, "WTF", "Account", name, "SavedVariables")
    os.makedirs(acc("NEW"))  # an account that never logged in with Brag
    os.makedirs(acc("OLD"))
    old = os.path.join(acc("OLD"), "Brag.lua")
    with open(old, "w") as f:
        f.write('BragDB = {\n["enabled"] = false,\n}\nBragHistory = {\n{\n["time"] = 5,\n["text"] = "Level 2!",\n},\n}\n')
    os.utime(old, (1_700_000_000, 1_700_000_000))
    checked = {}
    watch.mark_companion(game, checked)
    new = os.path.join(acc("NEW"), "Brag.lua")
    assert watch.load_saved(game)[0] == {"enabled": False, "companion": True}
    assert watch.load_saved(game)[1] == [{"time": 5, "text": "Level 2!"}]  # the history is kept
    assert os.path.getmtime(old) == 1_700_000_000  # still the account WoW saved last
    with open(new) as f:
        assert watch.parse_saved(f.read())[0] == {"companion": True}
    assert watch.settings_file(game) == old  # a file only the companion wrote isn't WoW's
    with open(old, "w") as f:
        f.write('BragDB = {\n["enabled"] = true,\n}\n')  # WoW, running since before, logs out and drops it
    watch.mark_companion(game, checked)
    assert watch.load_saved(game)[0] == {"enabled": True, "companion": True}
    real_save, watch.save_settings = watch.save_settings, lambda *a: (_ for _ in ()).throw(AssertionError("rewrote"))
    try:
        watch.mark_companion(game, checked)  # nothing changed: nothing rewritten
        watch.mark_companion(game, {})  # already marked: nothing rewritten either
    finally:
        watch.save_settings = real_save

with tempfile.TemporaryDirectory() as game:  # a new player: the marker alone doesn't tick "played"
    os.makedirs(os.path.join(game, "WTF", "Account", "ME", "SavedVariables"))
    watch.mark_companion(game, {})
    assert watch.settings_file(game) is None and not watch.state(game)["setup"]["played"] and not watch.state(game)["found"]

print("ok")
