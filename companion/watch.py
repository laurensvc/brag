#!/usr/bin/env python3
"""Brag companion: posts new WoW screenshots to Discord and serves a local page for
settings, past screenshots and event history (works with WoW closed).

Usage: python3 watch.py "<WoW install>/_forever_"   (opens http://127.0.0.1:8765)
"""
import glob, json, os, re, subprocess, sys, threading, time, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "brag-log.jsonl")
IMAGES = (".jpg", ".png")
DEFAULTS = {"enabled": True, "level": True, "quest": True, "loot": True, "minQuality": 4, "webhook": ""}
# Strict on purpose: the URL is handed to curl and written back into a Lua file.
WEBHOOK = re.compile(r"^https://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
ENTRY = re.compile(r'\["(\w+)"\]\s*=\s*("(?:[^"\\]|\\.)*"|[^,\n]+),')
BRAGDB = re.compile(r"^BragDB = \{.*?^\}$", re.S | re.M)
HISTORY = re.compile(r"^BragHistory = \{(.*?)^\}$", re.S | re.M)
CODES = re.compile(r"\|c(?:[0-9a-fA-F]{8}|n[^:]*:)|\|r|\|H[^|]*\|h|\|h")  # WoW color/link codes


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


def save_settings(path, new):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    db, _ = parse_saved(text)
    block = lua_db({**db, **new})
    text, n = BRAGDB.subn(lambda _: block, text, count=1)
    if not n:
        text = block + "\n" + text
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)  # never leave a half-written file: it also holds the history


def validate(s):
    """Return an error message, or None if the settings from the page are valid."""
    if not isinstance(s, dict) or set(s) != set(DEFAULTS):
        return "Bad request"
    if not all(isinstance(s[k], bool) for k in ("enabled", "level", "quest", "loot")):
        return "Bad request"
    if type(s["minQuality"]) is not int or not 2 <= s["minQuality"] <= 5:
        return "Minimum quality must be Uncommon to Legendary"
    if not isinstance(s["webhook"], str) or (s["webhook"] and not WEBHOOK.match(s["webhook"])):
        return "That isn't a Discord webhook URL"
    return None


# --- Discord posting ---

def log(name, status):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "status": status, "time": time.time()}) + "\n")


def statuses():
    out = {}
    try:
        with open(LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    out[e["name"]] = e["status"]
                except (ValueError, KeyError):
                    pass
    except FileNotFoundError:
        pass
    return out


def watch(game_dir):
    shots = os.path.join(game_dir, "Screenshots")
    seen = set(os.listdir(shots))
    while True:
        time.sleep(2)
        for name in sorted(set(os.listdir(shots)) - seen):
            seen.add(name)
            if not name.lower().endswith(IMAGES):
                continue
            db, _ = load_saved(game_dir)  # re-read each time so settings changes apply
            webhook = db.get("webhook", "")
            if not db.get("enabled", True):
                status = "skipped: Brag disabled"
            elif not WEBHOOK.match(webhook):
                status = "skipped: no webhook set"
            else:
                time.sleep(1)  # let WoW finish writing the file
                r = subprocess.run(["curl", "-sSf", "-F", f"file=@{os.path.join(shots, name)}", webhook])
                status = "posted" if r.returncode == 0 else "failed"
            log(name, status)
            print(f"{status}: {name}")


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
    return {
        "found": settings_file(game_dir) is not None,
        "settings": {**DEFAULTS, **{k: db[k] for k in DEFAULTS if k in db}},
        "shots": [{
            "name": n, "time": times[n], "status": done.get(n, ""),
            # the addon logs the event right before its screenshot
            "caption": next((h["text"] for h in history if isinstance(h.get("time"), (int, float)) and abs(h["time"] - times[n]) <= 3), ""),
        } for n in newest],
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
        if self.path != "/api/settings":
            return self.send(404, "{}")
        try:
            new = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            new = None
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
