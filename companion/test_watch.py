import os, tempfile
from watch import CODES, DEFAULTS, WEBHOOK, parse_saved, save_settings, validate

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

# saving rewrites BragDB but keeps the history and unknown keys intact
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "Brag.lua")
    with open(path, "w") as f:
        f.write(SAVED.replace('["minQuality"] = 4,', '["minQuality"] = 4,\n["future"] = "x",'))
    save_settings(path, {**DEFAULTS, "minQuality": 3})
    db2, history2 = parse_saved(open(path).read())
    assert db2 == {**DEFAULTS, "minQuality": 3, "future": "x"}, db2
    assert history2 == history

print("ok")
