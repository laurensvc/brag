# Brag — Discord posts for WoW Forever

WoW addons are sandboxed: they can't make network calls, and they only write files when you log out.
So there are two parts:

1. **Brag** (the addon) shows a banner and takes a screenshot when you level up, turn in a quest, or loot an epic+ item.
2. **companion/watch.py** watches your Screenshots folder and uploads every new screenshot to a Discord webhook,
   with a caption like "💎 **Thrall** looted **[Thunderfury]** (Legendary) · Level 60 Shaman · Molten Core".

## Setup
1. Download `Brag-<version>.zip` from the [latest release](https://github.com/laurensvc/brag/releases/latest) (or CurseForge)
   and unzip it into `<WoW install>/_forever_/Interface/AddOns/`, so you get `AddOns/Brag/Brag.toc`.
   Using GitHub's "Download ZIP" instead? Copy only the `Brag` folder inside `brag-main`: WoW ignores an addon
   whose folder name doesn't match its `.toc` file ("Folder brag-main must contain a file named brag-main.toc").
2. Check the interface number in game with `/dump select(4, GetBuildInfo())` and put it in `Brag.toc`,
   or tick "Load out of date AddOns".
3. Start the companion. It needs Python 3 and Pillow (curl ships with macOS and Windows 10+).
   Point it at your Forever game folder, the one that holds `Screenshots` and `WTF`:
   ```
   python3 -m pip install pillow
   python3 companion/watch.py "<WoW install>/_forever_"
   ```
   On Windows: `py -m pip install pillow`, then `py companion\watch.py "C:\...\_forever_"`

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
- The **Posting** settings on the page (caption, retries, max image size, JPEG quality, how many days of post
  history to keep, and optionally deleting older screenshots) belong to the companion and apply right away.

## How captions work
WoW only writes files at logout, so the addon can't tell the companion what just happened. Instead, for the
moment it takes a screenshot, Brag draws a thin strip of black and white blocks in the top-left corner that
encodes the event, your character, level, zone and the quest or item. The companion decodes it, crops it off
and posts the caption with the image. Screenshots you take yourself have no strip and go out without a caption.
The strip format is documented next to `drawStrip` in `Brag/Brag.lua` and `read_strip` in `companion/watch.py`.

## Testing without WoW
`companion/fakewow.py` runs the real addon in Lua 5.1 with a mock of the WoW API. It renders the screenshots
WoW would take (banner and data strip included) and writes SavedVariables like a logout, so the real
companion can post them to Discord:
```
python3 -m pip install lupa pillow
python3 companion/fakewow.py fake-wow --webhook "https://discord.com/api/webhooks/..."   # /brag: paste, Save & reload
python3 companion/watch.py fake-wow                                                     # in a second terminal
python3 companion/fakewow.py fake-wow demo        # quest turn-in that levels up, a legendary, a Test post
python3 companion/fakewow.py fake-wow level "quest=Bounty on Murlocs" "loot=Krol Blade:epic" print
```
Options: `--size 2560x1440`, `--ui-scale 0.71`, `--name`, `--zone`; `python3 companion/fakewow.py --help` lists the events.
The mock only knows the API calls Brag makes and draws an idealized frame, so check real rendering in game.

Tests: `python3 companion/test_watch.py` and `python3 companion/test_addon.py` (`py` on Windows)

## Releasing to CurseForge
Pushing to `main` runs the tests. If the `## Version:` in `Brag/Brag.toc` is new (there's no `v<version>` tag yet),
GitHub Actions zips `Brag/`, uploads it to CurseForge as a release for the game version that matches `## Interface:`
(16001 → 1.60.1), then tags it and creates a GitHub release with that zip and the commit list as changelog.
Pushes that don't bump the version only run the tests.

One-time setup:
```
gh secret set CF_API_TOKEN      # token from https://legacy.curseforge.com/account/api-tokens
gh variable set CF_PROJECT_ID   # numeric id from "About Project" on the CurseForge page
```
Without them the workflow still makes the GitHub release and skips CurseForge with a warning. To retry a failed upload: Actions → Test and release → Run workflow.
