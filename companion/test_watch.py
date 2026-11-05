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
assert caption("2\tfuture\tformat") == caption(None) == caption("1\tdance\ta\tb\tc\td\te\tf") == ""


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
assert post("x.jpg", "hi", HOOK, 3, run, sleeps.append) == "posted after 1 retry" and sleeps == [1.5]
run, calls, sleeps = fake_curl(*[(502, "")] * 4)
assert post("x.jpg", "hi", HOOK, 3, run, sleeps.append) == "failed: Discord had a problem (HTTP 502) after 3 retries"
assert sleeps == [2, 4, 8] and len(calls) == 4
run, calls, sleeps = fake_curl((0, ""), (204, ""))
assert post("x.jpg", "hi", HOOK, 1, run, sleeps.append) == "posted after 1 retry"
run, calls, sleeps = fake_curl((404, '{"message": "Unknown Webhook"}'))
assert post("x.jpg", "hi", HOOK, 3, run, sleeps.append) == "failed: webhook was deleted (HTTP 404)" and not sleeps
run, calls, sleeps = fake_curl((0, ""))
assert post("x.jpg", "hi", HOOK, 0, run, sleeps.append) == "failed: curl: (7) Failed to connect" and len(calls) == 1

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
assert status == "posted", status
body = received["body"]
sent = json.loads(body.split(b'name="payload_json"')[1].split(b"\r\n\r\n", 1)[1].split(b"\r\n--")[0])
assert sent == {"content": caption(QUEST), "allowed_mentions": {"parse": []}}, sent
assert b'filename="WoWScrnShot_110426_201500.jpg"' in body and b"\xff\xd8" in body


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
    real_post, watch.post = watch.post, lambda path, text, hook, retries: posted.append((Image.open(path).copy(), text, hook, retries)) or "posted"
    status, text = watch.handle(game, "WoWScrnShot_1.jpg")
    watch.post = real_post
    img, sent, hook, retries = posted[0]
    assert (status, text, sent, hook, retries) == ("posted", caption(LOOT, md=False), caption(LOOT), HOOK, 3)
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
        f.write("garbage\n")
    old = os.path.join(game, "Screenshots", "old.jpg")
    noisy(8, 8).save(old)
    os.utime(old, (now - 8 * 86400, now - 8 * 86400))
    assert cleanup(game, COMPANION_DEFAULTS, now) == 0 and os.path.exists(old)  # screenshots kept by default
    assert list(watch.statuses()) == ["new"]
    assert cleanup(game, {**COMPANION_DEFAULTS, "deleteShots": True}, now) == 1
    assert sorted(os.listdir(os.path.join(game, "Screenshots"))) == ["WoWScrnShot_1.jpg"]

assert watch.open_when_ready("missing.jpg", timeout=1, sleep=lambda s: None) is None


# --- the watcher: pausing, switching WoW folders, telling listeners ---

with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
    watch.LOG, watch.CONFIG = os.path.join(a, "log.jsonl"), os.path.join(a, "cfg.json")
    results, handled = [], []
    real_handle, watch.handle = watch.handle, lambda game, name: handled.append((game, name)) or ("posted", "cap")
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
        assert handled == [(a, "one.jpg")] and results == [("one.jpg", "posted", "cap")]

        watch.PAUSED.set()
        noisy(8, 8).save(os.path.join(w.folder, "two.jpg"))
        w = watch.watch_once(w)
        watch.PAUSED.clear()
        w = watch.watch_once(w)  # skipped while paused, and not posted after resuming
        assert len(handled) == 1 and results[-1] == ("two.jpg", "skipped: paused", "")
        assert watch.statuses()["two.jpg"]["status"] == "skipped: paused"

        os.makedirs(os.path.join(b, "Screenshots"))
        noisy(8, 8).save(os.path.join(b, "Screenshots", "old.jpg"))  # already there when we switch: not posted
        watch.GAME_DIR = b
        w = watch.watch_once(w)
        noisy(8, 8).save(os.path.join(b, "Screenshots", "new.jpg"))
        w = watch.watch_once(w)
        assert handled[1:] == [(b, "new.jpg")]
        assert any("Watching" in line["text"] and b in line["text"] for line in watch.LINES)
        assert watch.state(b)["log"][0]["text"] == "posted: new.jpg (cap)"  # newest first
    finally:
        watch.handle, watch.GAME_DIR = real_handle, None
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
    assert json.loads(r.read())["gameDir"] == ""
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

print("ok")
