# Runs the real Brag/Brag.lua in Lua 5.1 (fakewow.py) and checks what the companion makes of its screenshots.
import os, tempfile
from PIL import Image
import watch
from fakewow import FakeWoW
from watch import caption, load_saved, read_strip

HOOK = "https://discord.com/api/webhooks/123/abc-DEF_9"


def captions(wow):
    out = []
    for path in wow.taken:
        payload, _ = read_strip(Image.open(path))
        out.append(caption(payload, md=False))
    return out


# Every event, at several screen sizes and UI scales: the strip decodes to the right caption.
for size, scale, quality in [((1920, 1080), 1.0, 30), ((2560, 1440), 0.71, 30), ((3840, 2160), 1.15, 20), ((1366, 768), 0.9, 15)]:
    with tempfile.TemporaryDirectory() as d:
        wow = FakeWoW(d, size, scale, quality, {"name": "Jaïna", "surname": "Proudmoore", "zone": "Theramore Isle"})
        wow.turn_in('The "Missing" Diplomat\tpart 1', levels_up=True)  # quest + ding: two screenshots, in order
        wow.loot("Thunderfury, Blessed Blade of the Windseeker", 5)
        wow.loot("Krol Blade", 4, cached=False)  # not in the item cache: quality from the link color
        wow.loot("Linen Cloth", 1)  # below the minimum quality: nothing
        wow.loot("Lucky Charm", 4, pushed=True)  # "You receive item:" (quest rewards, mail)
        wow.end_encounter("Ragnaros", killed=False)  # a wipe: nothing
        wow.end_encounter("Ragnaros")
        wow.die()
        wow.die("Hogger", "Fireball")
        wow.hit("Ragnaros", target="Party-1")  # someone else's hit doesn't count: nothing logged on you
        wow.die()
        wow.die("Defias Thug")
        wow.die("falling")
        wow.hit("Hogger")
        wow.advance(20)  # a hit long before dying isn't the killer
        wow.die()
        wow.print_screen()  # the player's own screenshot: no strip
        assert captions(wow) == [
            "📜 Jaïna Proudmoore completed The \"Missing\" Diplomat part 1 · Level 41 Shaman · Theramore Isle",
            "🎉 Jaïna Proudmoore reached level 42! · Shaman · Theramore Isle",
            "💎 Jaïna Proudmoore looted [Thunderfury, Blessed Blade of the Windseeker] (Legendary) · Level 42 Shaman · Theramore Isle",
            "💎 Jaïna Proudmoore looted [Krol Blade] (Epic) · Level 42 Shaman · Theramore Isle",
            "💎 Jaïna Proudmoore looted [Lucky Charm] (Epic) · Level 42 Shaman · Theramore Isle",
            "⚔️ Jaïna Proudmoore defeated Ragnaros! · Level 42 Shaman · Theramore Isle",
            "💀 Jaïna Proudmoore died · Level 42 Shaman · Theramore Isle",
            "💀 Jaïna Proudmoore died to Hogger's Fireball · Level 42 Shaman · Theramore Isle",
            "💀 Jaïna Proudmoore died · Level 42 Shaman · Theramore Isle",
            "💀 Jaïna Proudmoore died to Defias Thug · Level 42 Shaman · Theramore Isle",
            "💀 Jaïna Proudmoore died to Falling · Level 42 Shaman · Theramore Isle",
            "💀 Jaïna Proudmoore died · Level 42 Shaman · Theramore Isle",
            "",
        ], (size, scale, captions(wow))

with tempfile.TemporaryDirectory() as d:
    # /brag opens the panel on the first try; typing the webhook and Save & reload writes it to SavedVariables
    wow = FakeWoW(d)
    wow.slash()
    assert wow.lua.globals().BragPanel.IsShown(wow.lua.globals().BragPanel)
    wow.type_webhook(HOOK)
    wow.click("Save & reload")
    db, history = load_saved(d)
    assert db["webhook"] == HOOK and db["enabled"] is True and history == [], (db, history)

    # Test post closes the panel and screenshots with its own caption
    wow.slash()
    wow.click("Test post")
    assert captions(wow) == ["✅ Brag test from Thrall: if you can read this, you're all set! · Level 41 Shaman · Orgrimmar"]
    assert not wow.lua.globals().BragPanel.IsShown(wow.lua.globals().BragPanel)

    # a very long quest title is cut to fit the strip without breaking it
    wow.turn_in("Ä" * 200)
    text = captions(wow)[-1]
    assert text.startswith("📜 Thrall completed ÄÄÄ") and len(text.encode()) < 300, text

    # the companion posts it with the strip cropped off and the caption attached
    wow.logout()
    posted = []
    real_post, watch.post = watch.post, lambda path, text, hook, retries: posted.append((Image.open(path).copy(), text, hook)) or watch.Result("posted")
    watch.CONFIG = os.path.join(d, "cfg.json")
    try:
        status, plain = watch.handle(d, os.path.basename(wow.taken[0]))
    finally:
        watch.post = real_post
    img, sent, hook = posted[0]
    assert status == watch.Result("posted") and hook == HOOK and sent.startswith("✅ Brag test from **Thrall**")
    assert img.height < 1080 and read_strip(img) == (None, 0)

    # history survives logout, and turning Brag off stops screenshots
    _, history = load_saved(d)
    assert [h["text"] for h in history] == ["Brag test: if this shows up in Discord, you're all set!", "Quest complete: " + "Ä" * 200]
    wow.lua.globals().BragDB.enabled = False
    before = len(wow.taken)
    wow.level_up()
    assert len(wow.taken) == before

    # each event has its own switch: deaths and boss kills too
    wow.lua.globals().BragDB.enabled = True
    wow.lua.globals().BragDB.death = False
    wow.lua.globals().BragDB.boss = False
    wow.die()
    wow.end_encounter("Onyxia")
    assert len(wow.taken) == before
    wow.lua.globals().BragDB.death = True
    wow.die()
    assert len(wow.taken) == before + 1 and wow.lua.globals().BragHistory[3].text == "Died in Orgrimmar"
    wow.die("Hogger")
    assert wow.lua.globals().BragHistory[4].text == "Died to Hogger in Orgrimmar"

with tempfile.TemporaryDirectory() as d:
    # an addon from before deaths and boss kills: its saved settings get them, switched on
    os.makedirs(os.path.join(d, "WTF", "Account", "FAKEWOW", "SavedVariables"))
    with open(os.path.join(d, "WTF", "Account", "FAKEWOW", "SavedVariables", "Brag.lua"), "w") as f:
        f.write('BragDB = {\n["enabled"] = true,\n["loot"] = false,\n["webhook"] = "",\n}\n')
    wow = FakeWoW(d)
    assert wow.db["boss"] is True and wow.db["death"] is True and wow.db["loot"] is False
    # and the /brag panel has the switches
    wow.slash()
    assert wow.lua.globals().MOCK_find("FontString", "Boss kills") and wow.lua.globals().MOCK_find("FontString", "Deaths")

# a new character with no SavedVariables yet gets the defaults
with tempfile.TemporaryDirectory() as d:
    assert FakeWoW(d).db == {"enabled": True, "level": True, "quest": True, "loot": True, "boss": True, "death": True,
                             "minQuality": 4, "webhook": ""}

print("ok")
