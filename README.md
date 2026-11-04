# Brag — Discord posts for WoW Forever

WoW addons are sandboxed: they can't make network calls, and they only write files when you log out.
So there are two parts:

1. **Brag** (the addon) shows a banner and takes a screenshot when you level up, turn in a quest, or loot an epic+ item.
2. **companion/watch.py** watches your Screenshots folder and uploads every new screenshot to a Discord webhook.

## Setup
1. Copy `Brag/` to `<WoW install>/_forever_/Interface/AddOns/` (use the folder your Forever client actually uses).
2. Check the interface number in game with `/dump select(4, GetBuildInfo())` and put it in `Brag.toc`,
   or tick "Load out of date AddOns".
3. Start the companion (needs Python 3; curl ships with macOS and Windows 10+).
   Point it at your Forever game folder, the one that holds `Screenshots` and `WTF`:
   ```
   python3 companion/watch.py "<WoW install>/_forever_"
   ```
   On Windows: `py companion\watch.py "C:\...\_forever_"`

   It opens **http://127.0.0.1:8765** in your browser, where you can change settings, browse past
   screenshots (with what happened and whether they were posted) and see your Brag history. WoW doesn't need to be running.
4. Set your Discord webhook (Discord: Server Settings → Integrations → Webhooks → New Webhook → Copy URL),
   either on that page or in game with `/brag` → **Save & reload**.
5. Click **Test post** in `/brag` to check it all works. Keep the companion running while you play.

Good to know:
- WoW only reads and writes addon settings at login/logout. Change settings on the page while WoW is closed,
  or in game with `/brag`; otherwise WoW overwrites the page's changes when you log out.
- In-game events reach the page's history after you log out or `/reload`; screenshots and post status show up live.
- Screenshots you take yourself (Print Screen) also get posted, unless Brag is disabled.
- The page only listens on your own computer (127.0.0.1) and rejects requests from other websites.

Tests: `python3 companion/test_watch.py`
