# Brag — Discord posts for WoW Forever

WoW addons are sandboxed: they can't make network calls, and they only write files when you log out.
So there are two parts:

1. **Brag** (the addon) shows a banner and takes a screenshot when you level up, turn in a quest, or loot an epic+ item.
2. **companion/watch.py** watches your Screenshots folder and uploads every new screenshot to a Discord webhook.

## Setup
1. Copy `Brag/` to `<WoW install>/_forever_/Interface/AddOns/` (use the folder your Forever client actually uses).
2. Check the interface number in game with `/dump select(4, GetBuildInfo())` and put it in `Brag.toc`,
   or tick "Load out of date AddOns".
3. In Discord: Server Settings → Integrations → Webhooks → New Webhook → Copy URL.
4. Run the companion while you play (needs Python 3; curl ships with macOS and Windows 10+):
   ```
   DISCORD_WEBHOOK=<url> python3 companion/watch.py "<WoW install>/_forever_/Screenshots"
   ```
   On Windows PowerShell: `$env:DISCORD_WEBHOOK="<url>"; py companion\watch.py "C:\...\_forever_\Screenshots"`

Change `MIN_QUALITY` at the top of `Brag.lua` to post rare (3) drops too.
Screenshots you take yourself (Print Screen) also get posted.
