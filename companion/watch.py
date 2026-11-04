#!/usr/bin/env python3
"""Brag companion: posts new WoW screenshots to Discord and serves a local page for
settings, past screenshots and event history (works with WoW closed).

Usage: python3 watch.py "<WoW install>/_forever_"   (opens http://127.0.0.1:8765)
Needs Pillow: python3 -m pip install pillow
"""
import glob, json, math, os, re, subprocess, sys, tempfile, threading, time, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from PIL import Image
except ImportError:
    sys.exit("Brag needs Pillow to read screenshots. Install it with:  python3 -m pip install pillow")

PORT = 8765
ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "brag-log.jsonl")
CONFIG = os.path.join(HERE, "brag-companion.json")
IMAGES = (".jpg", ".jpeg", ".png", ".tga")
DEFAULTS = {"enabled": True, "level": True, "quest": True, "loot": True, "minQuality": 4, "webhook": ""}
# Settings only the companion uses, so they live in its own file and can be changed while WoW runs.
COMPANION_DEFAULTS = {"caption": True, "retries": 3, "maxHeight": 1080, "jpegQuality": 85, "keepDays": 7, "deleteShots": False}
HEIGHTS = (0, 720, 1080, 1440, 2160)  # 0 = keep the original size
MAX_BYTES = 8 * 1024 * 1024  # smallest Discord webhook upload limit (servers without boosts)
QUALITY = {0: "Poor", 1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary", 6: "Artifact"}
# Strict on purpose: the URL is handed to curl and written back into a Lua file.
WEBHOOK = re.compile(r"^https://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
ENTRY = re.compile(r'\["(\w+)"\]\s*=\s*("(?:[^"\\]|\\.)*"|[^,\n]+),')
BRAGDB = re.compile(r"^BragDB = \{.*?^\}$", re.S | re.M)
HISTORY = re.compile(r"^BragHistory = \{(.*?)^\}$", re.S | re.M)
CODES = re.compile(r"\|c(?:[0-9a-fA-F]{8}|n[^:]*:)|\|r|\|H[^|]*\|h|\|h")  # WoW color/link codes
MARKDOWN = re.compile(r"([\\*_~`|<>\[\]()])")
LOG_LOCK = threading.Lock()


# --- Brag's SavedVariables file (WTF/Account/<name>/SavedVariables/Brag.lua) ---

def lua_value(v):
    if v.startswith('"'):
        return re.sub(r"\\(.)", lambda m: "\n" if m.group(1) == "n" else m.group(1), v[1:-1])
    if v in ("true", "false"):
        return v == "true"
    try:
        return int(v)
    except ValueError:
        return float(v)


def lua_string(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def parse_saved(text):
    """Return (BragDB dict, BragHistory list) from the SavedVariables file text."""
    m = BRAGDB.search(text)
    db = {k: lua_value(v) for k, v in ENTRY.findall(m.group(0))} if m else {}
    h = HISTORY.search(text)
    # shortcut: assumes history texts contain no { or }; true for quest and item names
    entries = re.findall(r"\{([^{}]*)\}", h.group(1)) if h else []
    return db, [{k: lua_value(v) for k, v in ENTRY.findall(e)} for e in entries]


def lua_db(db):
    val = lambda v: ("true" if v else "false") if isinstance(v, bool) else lua_string(v) if isinstance(v, str) else str(v)
    return "BragDB = {\n" + "".join(f'["{k}"] = {val(v)},\n' for k, v in db.items()) + "}"


def settings_file(game_dir):
    # shortcut: with several WoW accounts we use the most recently saved one; add an account picker if that bites
    files = glob.glob(os.path.join(game_dir, "WTF", "Account", "*", "SavedVariables", "Brag.lua"))
    return max(files, key=os.path.getmtime) if files else None


def load_saved(game_dir):
    path = settings_file(game_dir)
    if not path:
        return {}, []
    with open(path, encoding="utf-8", errors="replace") as f:
        return parse_saved(f.read())


def write_atomic(path, text):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)  # never leave a half-written file


def save_settings(path, new):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    db, _ = parse_saved(text)
    block = lua_db({**db, **new})
    text, n = BRAGDB.subn(lambda _: block, text, count=1)
    if not n:
        text = block + "\n" + text
    write_atomic(path, text)  # the file also holds the history


def validate(s):
    """Return an error message, or None if the in-game settings from the page are valid."""
    if not isinstance(s, dict) or set(s) != set(DEFAULTS):
        return "Bad request"
    if not all(isinstance(s[k], bool) for k in ("enabled", "level", "quest", "loot")):
        return "Bad request"
    if type(s["minQuality"]) is not int or not 2 <= s["minQuality"] <= 5:
        return "Minimum quality must be Uncommon to Legendary"
    if not isinstance(s["webhook"], str) or (s["webhook"] and not WEBHOOK.match(s["webhook"])):
        return "That isn't a Discord webhook URL"
    return None


# --- Companion settings (brag-companion.json) ---

def validate_companion(s):
    """Return an error message, or None if the companion settings are valid."""
    if not isinstance(s, dict) or set(s) != set(COMPANION_DEFAULTS):
        return "Bad request"
    if not all(isinstance(s[k], bool) for k in ("caption", "deleteShots")):
        return "Bad request"
    num = lambda k, lo, hi: type(s[k]) is int and lo <= s[k] <= hi
    if not num("retries", 0, 3):
        return "Retries must be 0 to 3"
    if s["maxHeight"] not in HEIGHTS or type(s["maxHeight"]) is not int:
        return "Pick a size from the list"
    if not num("jpegQuality", 40, 95):
        return "JPEG quality must be 40 to 95"
    if not num("keepDays", 1, 365):
        return "Keep history for 1 to 365 days"
    return None


def load_companion():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            saved = json.load(f)
        cfg = {**COMPANION_DEFAULTS, **{k: saved[k] for k in COMPANION_DEFAULTS if k in saved}}
    except (OSError, ValueError, TypeError):
        return dict(COMPANION_DEFAULTS)
    return cfg if validate_companion(cfg) is None else dict(COMPANION_DEFAULTS)


def save_companion(cfg):
    write_atomic(CONFIG, json.dumps(cfg, indent=2))


# --- Reading the screenshot: Brag's data strip (see drawStrip in Brag.lua) ---

def fletcher(data):
    s1 = s2 = 0
    for b in data:
        s1 = (s1 + b) % 255
        s2 = (s2 + s1) % 255
    return bytes((s1, s2))


def strip_bytes(gray, block, start, count, per_row):
    """Read `count` bytes from the strip, starting at byte `start`; None if it runs off the image."""
    px, out = gray.load(), bytearray()
    for i in range(start * 8, (start + count) * 8):
        x, y = int((i % per_row + 0.5) * block), int((i // per_row + 0.5) * block)
        if not (1 <= x < gray.width - 1 and 1 <= y < gray.height - 1):
            return None
        on = sum(px[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1)) > 9 * 127  # 3x3 average beats JPEG noise
        if i % 8 == 0:
            out.append(0)
        out[-1] = out[-1] << 1 | on
    return bytes(out)


def read_strip(img):
    """Return (payload, strip height in pixels), or (None, 0) for screenshots without a strip."""
    gray = img.crop((0, 0, img.width, min(img.height, 600))).convert("L")
    # Blocks are 8 pixels unless the screenshot is scaled (render scale, odd clients): then search.
    for block in [8.0] + [b / 20 for b in range(80, 641) if b != 160]:
        if strip_bytes(gray, block, 0, 2, 10**9) != b"Bg":  # cheap check first: most sizes fail here
            continue
        head = strip_bytes(gray, block, 0, 5, 10**9)  # the header always fits in the first row
        if not head or not head[2] << 8 | head[3]:
            continue
        per_row, n = head[2] << 8 | head[3], head[4]
        # A rough block size reads the short header, but drifts over a full row. The strip spans the screen
        # width minus under 8 pixels, so the exact size is width / (per_row + 0..7/8).
        for exact in [block] + [img.width / (per_row + f / 8) for f in range(8)]:
            body = strip_bytes(gray, exact, 5, n + 2, per_row)
            if body and fletcher(body[:n]) == body[n:]:
                rows = math.ceil((7 + n) * 8 / per_row)
                return body[:n].decode("utf-8", "ignore"), math.ceil(rows * exact) + 1  # +1: blurred edge
    return None, 0


def caption(payload, md=True):
    """Turn the strip payload into the post text: Discord markdown, or plain for the page."""
    f = (payload or "").split("\t")
    if len(f) < 8 or f[0] != "1":
        return ""
    _, kind, name, cls, level, zone, detail, quality = f[:8]
    esc = (lambda s: MARKDOWN.sub(r"\\\1", s)) if md else (lambda s: s)
    bold = (lambda s: f"**{esc(s)}**") if md else esc
    who = bold(name or "Someone")
    q = QUALITY.get(int(quality)) if quality.isdigit() else None
    head = {
        "level": f"🎉 {who} reached {bold('level ' + level)}!",
        "quest": f"📜 {who} completed {bold(detail)}",
        "loot": f"💎 {who} looted {bold('[' + detail + ']')}" + (f" ({q})" if q else ""),
        "test": f"✅ Brag test from {who}: if you can read this, you're all set!",
    }.get(kind)
    if not head:
        return ""
    info = " · ".join(esc(x) for x in (cls if kind == "level" else f"Level {level} {cls}".strip(), zone) if x)
    if not info:
        return head
    return f"{head}\n-# {info}" if md else f"{head} · {info}"


def open_when_ready(path, timeout=15, sleep=time.sleep):
    """Wait until WoW has finished writing the file (same size twice and it decodes), then open it."""
    last = -1
    for _ in range(int(timeout * 2)):
        sleep(0.5)
        try:
            size = os.path.getsize(path)
            if size and size == last:
                img = Image.open(path)
                img.load()
                return img
            last = size
        except OSError:  # still being written, or locked by WoW
            last = -1
    return None


def prepare(img, cfg, out):
    """Write the image to `out` as a JPEG, scaled down to the max height and under Discord's size limit."""
    if cfg["maxHeight"] and img.height > cfg["maxHeight"]:
        h = cfg["maxHeight"]
        img = img.resize((round(img.width * h / img.height), h), Image.LANCZOS)
    img = img.convert("RGB")
    for q in sorted({cfg["jpegQuality"], 70, 55, 40} - set(range(cfg["jpegQuality"] + 1, 101)), reverse=True):
        img.save(out, "JPEG", quality=q, optimize=True)
        if os.path.getsize(out) <= MAX_BYTES:
            return


# --- Discord posting ---

def failure(code, body, err):
    if code == 0:
        return (err.strip().splitlines() or ["no connection"])[-1]
    return {
        400: "Discord rejected the post", 401: "webhook is invalid", 404: "webhook was deleted",
        413: "file too large", 429: "rate limited",
    }.get(code, "Discord had a problem" if code >= 500 else "unexpected response") + f" (HTTP {code})"


def post(path, text, webhook, retries, run=subprocess.run, sleep=time.sleep):
    """Upload one image, retrying rate limits and server/network errors. Returns the status for the log."""
    with tempfile.TemporaryDirectory() as d:
        payload = os.path.join(d, "payload.json")
        with open(payload, "w", encoding="utf-8") as f:  # a file, not an argument: keeps emoji and accents intact on Windows
            json.dump({"content": text, "allowed_mentions": {"parse": []}}, f)  # no @everyone from item names
        slash = lambda p: p.replace("\\", "/")  # curl reads \ inside quotes as an escape; Windows accepts /
        cmd = ["curl", "-sS", "--max-time", "60", "-o", "-", "-w", "\n%{http_code}",
               "-F", f'payload_json=<"{slash(payload)}";type=application/json',
               "-F", f'files[0]=@"{slash(path)}";filename="{os.path.basename(path)}"', webhook]
        for attempt in range(retries + 1):
            r = run(cmd, capture_output=True, encoding="utf-8", errors="replace")
            body, _, code = r.stdout.rpartition("\n")
            code = int(code) if code.strip().isdigit() else 0
            if 200 <= code < 300:
                return "posted" + (f" after {attempt} {'retry' if attempt == 1 else 'retries'}" if attempt else "")
            if code == 429:
                try:
                    wait = float(json.loads(body)["retry_after"])
                except (ValueError, KeyError, TypeError):
                    wait = 5
            elif code == 0 or code >= 500:
                wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
            else:
                return "failed: " + failure(code, body, r.stderr)  # retrying won't fix a bad webhook or a huge file
            if attempt < retries:
                sleep(min(wait, 60))
        tried = f" after {retries} {'retry' if retries == 1 else 'retries'}" if retries else ""
        return "failed: " + failure(code, body, r.stderr) + tried


def log(name, status, text=""):
    with LOG_LOCK, open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "status": status, "caption": text, "time": time.time()}) + "\n")


def statuses():
    out = {}
    try:
        with LOG_LOCK, open(LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    out[e["name"]] = e
                except (ValueError, KeyError, TypeError):
                    pass
    except FileNotFoundError:
        pass
    return out


def cleanup(game_dir, cfg, now=None):
    """Drop log entries older than keepDays and, if enabled, delete older screenshots. Returns files deleted."""
    cutoff = (now or time.time()) - cfg["keepDays"] * 86400

    def recent(line):
        try:
            return json.loads(line)["time"] >= cutoff
        except (ValueError, KeyError, TypeError):
            return False

    with LOG_LOCK:
        try:
            with open(LOG, encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []
        keep = [line for line in lines if recent(line)]
        if len(keep) != len(lines):
            write_atomic(LOG, "".join(keep))
    removed = 0
    if cfg["deleteShots"]:
        shots = os.path.join(game_dir, "Screenshots")
        for name in os.listdir(shots):
            path = os.path.join(shots, name)
            try:
                if name.lower().endswith(IMAGES) and os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                pass
    return removed


def handle(game_dir, name):
    """Read, caption and post one new screenshot. Returns (status, plain caption)."""
    img = open_when_ready(os.path.join(game_dir, "Screenshots", name))
    payload, crop = read_strip(img) if img else (None, 0)
    db, _ = load_saved(game_dir)  # re-read each time so settings changes apply
    cfg = load_companion()
    webhook = db.get("webhook", "")
    if not img:
        status = "failed: couldn't read the screenshot"
    elif not db.get("enabled", True):
        status = "skipped: Brag disabled"
    elif not WEBHOOK.match(webhook):
        status = "skipped: no webhook set"
    else:
        if crop:
            img = img.crop((0, crop, img.width, img.height))  # remove the data strip
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, os.path.splitext(name)[0] + ".jpg")
            prepare(img, cfg, out)
            status = post(out, caption(payload) if cfg["caption"] else "", webhook, cfg["retries"])
    return status, caption(payload, md=False)


def watch(game_dir):
    shots = os.path.join(game_dir, "Screenshots")
    seen = set(os.listdir(shots))
    cleaned = 0
    while True:
        if time.time() - cleaned > 3600:
            cleanup(game_dir, load_companion())
            cleaned = time.time()
        time.sleep(2)
        for name in sorted(set(os.listdir(shots)) - seen):
            seen.add(name)
            if not name.lower().endswith(IMAGES):
                continue
            try:
                status, text = handle(game_dir, name)
            except Exception as e:  # keep watching whatever happens to one file
                status, text = f"failed: {e}", ""
            log(name, status, text)
            print(f"{status}: {name}" + (f" ({text})" if text else ""))


# --- Local page ---

def state(game_dir):
    db, history = load_saved(game_dir)
    for h in history:
        h["text"] = CODES.sub("", str(h.get("text", "")))
    shots = os.path.join(game_dir, "Screenshots")
    times = {n: os.path.getmtime(os.path.join(shots, n)) for n in os.listdir(shots) if n.lower().endswith(IMAGES)}
    # shortcut: only the newest 60 screenshots are shown; add paging if people want to dig further back
    newest = sorted(times, key=times.get, reverse=True)[:60]
    done = statuses()

    def shot_caption(n):
        if done.get(n, {}).get("caption"):
            return done[n]["caption"]
        # older screenshots: the addon logs the event right before its screenshot
        return next((h["text"] for h in history if isinstance(h.get("time"), (int, float)) and abs(h["time"] - times[n]) <= 3), "")

    return {
        "found": settings_file(game_dir) is not None,
        "settings": {**DEFAULTS, **{k: db[k] for k in DEFAULTS if k in db}},
        "companion": load_companion(),
        "shots": [{"name": n, "time": times[n], "status": done.get(n, {}).get("status", ""), "caption": shot_caption(n)}
                  for n in newest],
        "history": history[::-1][:100],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        body = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def local(self):
        # stops other websites (incl. DNS rebinding) from reading screenshots or changing the webhook
        return "http://" + self.headers.get("Host", "") in ORIGINS

    def do_GET(self):
        if not self.local():
            return self.send(403, "{}")
        if self.path == "/":
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        if self.path == "/api/state":
            return self.send(200, json.dumps(state(GAME_DIR)))
        shots = os.path.join(GAME_DIR, "Screenshots")
        name = urllib.parse.unquote(self.path.removeprefix("/shots/"))
        if self.path.startswith("/shots/") and name in os.listdir(shots):  # listdir check blocks ../ paths
            with open(os.path.join(shots, name), "rb") as f:
                return self.send(200, f.read(), "image/png" if name.lower().endswith(".png") else "image/jpeg")
        self.send(404, "{}")

    def do_POST(self):
        if not self.local() or self.headers.get("Origin") not in ORIGINS:
            return self.send(403, "{}")
        if self.path not in ("/api/settings", "/api/companion"):
            return self.send(404, "{}")
        try:
            new = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            new = None
        if self.path == "/api/companion":
            error = validate_companion(new)
            if error:
                return self.send(400, json.dumps({"error": error}))
            save_companion(new)
            return self.send(200, json.dumps({"removed": cleanup(GAME_DIR, new)}))
        error = validate(new)
        path = settings_file(GAME_DIR)
        if not error and not path:
            error = "Log in to WoW once with Brag installed, so its settings file exists."
        if error:
            return self.send(400, json.dumps({"error": error}))
        save_settings(path, new)
        self.send(200, "{}")


def main():
    global GAME_DIR
    GAME_DIR = sys.argv[1]
    sys.stdout.reconfigure(errors="replace")  # captions have emoji; a cp1252 pipe or log file must not crash the watcher
    os.makedirs(os.path.join(GAME_DIR, "Screenshots"), exist_ok=True)  # WoW only creates it on the first screenshot
    threading.Thread(target=watch, args=(GAME_DIR,), daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Brag is running at {url} (Ctrl+C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
