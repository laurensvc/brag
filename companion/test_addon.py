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


def die(wow, *killer):
    """Die, get back up, and wait: deaths within 30 seconds of each other count as one."""
    wow.die(*killer)
    wow.revive()
    wow.advance(30)


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
        wow.end_encounter("Ragnaros")  # outside a dungeon or raid: a world boss, posted right away
        die(wow)
        die(wow, "Hogger", "Fireball")
        wow.hit("Ragnaros", target="Party-1")  # someone else's hit doesn't count: nothing logged on you
        die(wow)
        die(wow, "Defias Thug")
        die(wow, "falling")
        wow.hit("Hogger")
        wow.advance(20)  # a hit long before dying isn't the killer
        die(wow)
        wow.print_screen()  # the player's own screenshot: no strip
        assert captions(wow) == [
            "📜 Jaïna Proudmoore completed The \"Missing\" Diplomat part 1 · Level 41 Shaman · Theramore Isle",
            "🎉 Jaïna Proudmoore reached level 42! · ⏱️ 1d 3h played · Shaman · Theramore Isle",
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
    die(wow)
    wow.end_encounter("Onyxia")
    assert len(wow.taken) == before
    wow.lua.globals().BragDB.death = True
    die(wow)
    assert len(wow.taken) == before + 1 and wow.lua.globals().BragHistory[3].text == "Died in Orgrimmar"
    die(wow, "Hogger")
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
    assert wow.lua.globals().MOCK_find("FontString", "Dungeon and raid runs") and wow.lua.globals().MOCK_find("FontString", "Deaths")

# a new character with no SavedVariables yet gets the defaults
with tempfile.TemporaryDirectory() as d:
    assert FakeWoW(d).db == {"enabled": True, "level": True, "quest": True, "loot": True, "boss": True, "death": True,
                             "minQuality": 4, "webhook": ""}


# without the Brag app, the addon says posting needs it: in chat and in a window with the download link
with tempfile.TemporaryDirectory() as d:
    wow = FakeWoW(d)
    g = wow.lua.globals()
    assert "needs the free Brag app" in g.MOCK_chat[1] and not g.BragAppReminder
    wow.advance(5)
    link = g.BragAppReminder.link
    assert g.BragAppReminder.IsShown(g.BragAppReminder) and link.text.endswith("/BragSetup.exe") and link.highlighted
    link.scripts.OnTextChanged(link, True)  # typing in the box doesn't change the link
    assert link.text.endswith("/BragSetup.exe")
    wow.click("OK")
    wow.slash()
    wow.click("Get the app")  # /brag opens it again
    assert g.BragAppReminder.IsShown(g.BragAppReminder) and not g.BragPanel.IsShown(g.BragPanel)
    wow.click("Don't remind me")
    wow.logout()
    wow.login()
    wow.advance(5)
    g = wow.lua.globals()
    assert len(g.MOCK_chat) == 0 and not g.BragAppReminder  # it remembers

# once the app has run, no reminder and no Get the app button
with tempfile.TemporaryDirectory() as d:
    wow = FakeWoW(d)
    wow.logout()
    watch.mark_companion(d, {})
    wow.login()
    wow.advance(5)
    g = wow.lua.globals()
    assert wow.db["companion"] is True and len(g.MOCK_chat) == 0 and not g.BragAppReminder
    wow.slash()
    assert not g.MOCK_find("Button", "Get the app")
    wow.click("Test post")
    assert len(g.MOCK_chat) == 0
    wow.logout()
    assert load_saved(d)[0]["companion"] is True  # WoW keeps it at logout

# a new player: the app writes the marker before WoW ever saved Brag's settings
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "WTF", "Account", "FAKEWOW", "SavedVariables"))
    watch.mark_companion(d, {})
    wow = FakeWoW(d)
    wow.advance(5)
    assert wow.db["companion"] is True and wow.db["enabled"] is True and not wow.lua.globals().BragAppReminder

# WoW saying "you died" twice, or again while you're a ghost, posts and counts one death
with tempfile.TemporaryDirectory() as d:
    wow = FakeWoW(d)
    wow.die("Hogger")
    wow.fire("PLAYER_DEAD")  # 5 seconds later
    wow.advance(5)
    wow.release()
    wow.advance(60)
    wow.fire("PLAYER_DEAD")  # a minute later, as a ghost
    wow.advance(5)
    assert len(wow.taken) == 1 and wow.char["deaths"] == 1, (wow.taken, wow.char)
    # the same goes for any event; a test post always goes out
    wow.turn_in("Bounty on Murlocs")
    wow.turn_in("Bounty on Murlocs")
    for _ in range(2):
        wow.slash()
        wow.click("Test post")
    assert len(wow.taken) == 4

# dungeons and raids: no post per boss, one when you leave, with what happened inside
with tempfile.TemporaryDirectory() as d:
    wow = FakeWoW(d, player={"name": "Pierre", "level": 22, "zone": "The Barrens"})
    wow.lua.globals().BragDB.death = False  # only the run posts
    wow.enter("Wailing Caverns")
    wow.advance(600)
    wow.end_encounter("Lady Anacondra")
    wow.end_encounter("Lord Pythas", killed=False)  # a wipe
    wow.die("Deviate Lasher")
    wow.release()  # to the graveyard outside, as a ghost: the run goes on
    wow.revive("Wailing Caverns")  # the corpse run back in
    wow.logout()
    wow.login()  # a /reload or a relog inside keeps the run
    wow.lua.globals().BragDB.death = False
    wow.advance(1200)
    wow.end_encounter("Lord Pythas")
    assert wow.taken == []
    wow.leave()
    assert captions(wow) == ["🏰 Pierre finished Wailing Caverns! · ⚔️ 2 bosses · 1 wipe · 1 death · 30m · Level 22 Shaman · The Barrens"], captions(wow)
    wow.enter("Ragefire Chasm")
    wow.leave()  # no boss killed: nothing to brag about
    wow.enter("Molten Core", raid=True)
    wow.end_encounter("Lucifron")
    wow.die()
    wow.release()
    wow.revive()  # at the spirit healer, outside: the run is over
    assert captions(wow)[1:] == ["🐉 Pierre finished the raid Molten Core! · ⚔️ 1 boss · 1 death · 1m · Level 22 Shaman · The Barrens"], captions(wow)
    assert "run" not in wow.char
    wow.lua.globals().BragDB.boss = False  # the switch for runs
    wow.enter("Wailing Caverns")
    wow.end_encounter("Lady Anacondra")
    wow.leave()
    assert len(wow.taken) == 2

# level-ups say how long the level took, how often you died and your /played, without /played spam in chat
with tempfile.TemporaryDirectory() as d:
    wow = FakeWoW(d)  # /played at login: 100000 s, this level since 96400
    g = wow.lua.globals()
    wow.advance(3605)
    wow.level_up()
    die(wow)
    wow.advance(600)
    wow.level_up()
    assert captions(wow) == [
        "🎉 Thrall reached level 42! · ⏱️ Level 41 took 2h 00m · 1d 4h played · Shaman · Orgrimmar",  # deaths: Brag missed part of 41
        "💀 Thrall died · Level 42 Shaman · Orgrimmar",
        "🎉 Thrall reached level 43! · ⏱️ Level 42 took 10m · 1 death · 1d 4h played · Shaman · Orgrimmar",
    ], captions(wow)
    assert not any(line.startswith("Total time played") for line in g.MOCK_chat.values())
    g.RequestTimePlayed()  # the player's own /played still shows
    wow.advance(1)
    assert list(g.MOCK_chat.values())[-1].startswith("Total time played")
    wow.logout()
    wow.login()
    g = wow.lua.globals()
    g.MOCK_noPlayed = True  # the server doesn't answer: posted anyway, a second later
    wow.level_up()
    assert captions(wow)[-1] == "🎉 Thrall reached level 44! · ⏱️ no deaths · Shaman · Orgrimmar", captions(wow)

# a big drop: its tooltip is in the screenshot, and the post links the item on Wowhead
with tempfile.TemporaryDirectory() as d:
    wow = FakeWoW(d)
    wow.loot("Krol Blade", 4)
    wow.turn_in("Bounty on Murlocs")
    assert wow.tips[0].endswith("|h[Krol Blade]|h|r") and wow.tips[1] is None, wow.tips
    assert not wow.lua.globals().BragTooltip.IsShown(wow.lua.globals().BragTooltip)
    payload, _ = read_strip(Image.open(wow.taken[0]))
    assert caption(payload).startswith("💎 **Thrall** looted [**Krol Blade**](<https://www.wowhead.com/forever/item=19000>) (Epic)")

print("ok")
