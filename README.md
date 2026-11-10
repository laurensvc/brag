# Brag — Discord posts for WoW Forever

WoW addons are sandboxed: they can't make network calls, and they only write files when you log out.
So there are two parts:

1. **Brag** (the addon) shows a banner and takes a screenshot when you level up, turn in a quest, loot an epic+ item,
   finish a dungeon or raid, or die (each one can be switched off). Level-ups say how long the level took, how often
   you died and your /played; a finished run says how many bosses died, wipes, deaths and how long it took; a big
   drop shows the item's tooltip and links it on Wowhead.
2. **The companion** watches your Screenshots folder and uploads every new screenshot to a Discord webhook,
   with a caption like "💎 **Thrall** looted **[Thunderfury]** (Legendary) · Level 60 Shaman · Molten Core".
   On Windows it's a small tray app (**BragSetup.exe**); on Mac and Linux, the `companion/watch.py` script.

## Setup
### Windows: the easy way
1. Download **[BragSetup.exe](https://github.com/laurensvc/brag/releases/latest/download/BragSetup.exe)** and run it.
   No admin needed. Windows may warn about an unknown publisher: click **More info**, then **Run anyway**.
2. Brag opens with a **Setup** checklist that ticks itself off:
   1. **Find your WoW folder**: Brag looks for it itself, or asks you for the `_forever_` folder.
   2. **Install the Brag addon**: Brag copies its addon into WoW for you, and updates it when Brag updates.
   3. **Connect Discord**: paste the link Discord gives you (the page shows where to find it), then click
      **Send test message** to check it.
   4. **Play!** Brag waits in the tray next to the clock and posts while you play.

That's all. More about the tray app:
- click the icon to open the Brag window (setup, screenshots, history and a log of every post);
- closing the window keeps Brag running in the tray; right-click → **Quit** stops it;
- right-click also has **Pause posting**, **Open Screenshots folder** and **Start with Windows**;
- the icon is gold while it works, grey when paused or not set up yet (hover it to see why), and red with a
  Windows notification when a post fails.

Its settings and log live in `%APPDATA%\Brag`. Used the command-line companion before? Run
`Brag.exe --import "<the companion folder>"` once to bring over its posting settings and post history.

The window uses Microsoft Edge WebView2, which Windows 11 and up-to-date Windows 10 already have. Without it,
Brag says so once and shows its page in your browser instead (the tray works the same; type or paste your
WoW folder under Settings). Install [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703) and restart
Brag to get the window back. `Brag.exe --browser` always uses the browser.

### Mac and Linux (or Windows without the app)
1. Run the companion script. It needs Python 3 and Pillow (curl ships with macOS and Windows 10+). Point it at
   your Forever game folder, the one that holds `Screenshots` and `WTF`:
   ```
   python3 -m pip install pillow
   python3 companion/watch.py "<WoW install>/_forever_"
   ```
   On Windows: `py -m pip install pillow`, then `py companion\watch.py "C:\...\_forever_"`

   It installs the addon from this repo's `Brag` folder into WoW if it isn't there yet, and opens
   **http://127.0.0.1:8765**: the same page and Setup checklist as the Windows app. WoW doesn't need to be running.
2. Paste your Discord link under **Connect Discord** and click **Send test message**.

Installing the addon yourself (CurseForge, or `Brag-<version>.zip` from the
[latest release](https://github.com/laurensvc/brag/releases/latest)) works too, but posting still needs the app or
the script: until the addon sees it has run, it reminds you at login with the download link. Unzip it into
`<WoW install>/_forever_/Interface/AddOns/`, so you get `AddOns/Brag/Brag.toc`. Using GitHub's "Download ZIP"?
Copy only the `Brag` folder inside `brag-main`: WoW ignores an addon whose folder name doesn't match its `.toc`
file. If WoW calls the addon out of date, tick "Load out of date AddOns" on the character screen.

Good to know:
- The Discord link you paste on the page is kept by Brag and wins over one typed in game with `/brag`.
- WoW only reads and writes addon settings (what to post) at login/logout. Change those on the page while WoW
  is closed, or in game with `/brag`; otherwise WoW overwrites the page's changes when you log out.
- In-game events reach the page's history after you log out or `/reload`; screenshots and post status show up live.
- Screenshots you take yourself (Print Screen) also get posted, unless Brag is disabled.
- The page only listens on your own computer (127.0.0.1) and rejects requests from other websites.
- The **Advanced** settings on the page (caption, retries, max image size, JPEG quality, how many days of post
  history to keep, and optionally deleting older screenshots) belong to the companion and apply right away.

## How captions work
WoW only writes files at logout, so the addon can't tell the companion what just happened. Instead, for the
moment it takes a screenshot, Brag draws a thin strip of black and white blocks in the top-left corner that
encodes the event, your character, level, zone and the quest or item. The companion decodes it, crops it off
and posts the caption with the image. Screenshots you take yourself have no strip and go out without a caption.
The strip format is documented next to `drawStrip` in `Brag/Brag.lua` and `read_strip` in `companion/watch.py`.

By default each caption is a random joke line ("💀 **Pierre** found out what that red circle does"); switch
**Funny captions** off under Advanced for plain ones. The lines are in `companion/flavor.py`: add your own there.

## Testing without WoW
`companion/fakewow.py` runs the real addon in Lua 5.1 with a mock of the WoW API. It renders the screenshots
WoW would take (banner and data strip included) and writes SavedVariables like a logout, so the real
companion can post them to Discord:
```
python3 -m pip install lupa pillow
python3 companion/fakewow.py fake-wow --webhook "https://discord.com/api/webhooks/..."   # /brag: paste, Save & reload
python3 companion/watch.py fake-wow                                                     # in a second terminal
python3 companion/fakewow.py fake-wow demo        # quest turn-in that levels up, a legendary, a Test post
python3 companion/fakewow.py fake-wow level "quest=Bounty on Murlocs" "loot=Krol Blade:epic" boss=Onyxia death=Hogger:Fireball print
python3 companion/fakewow.py fake-wow run="Wailing Caverns"    # a dungeon: three bosses, a death, then leaving
```
Options: `--size 2560x1440`, `--ui-scale 0.71`, `--name`, `--zone`; `python3 companion/fakewow.py --help` lists the events.
The mock only knows the API calls Brag makes and draws an idealized frame, so check real rendering in game.

Tests: `python3 companion/test_watch.py` and `python3 companion/test_addon.py` (`py` on Windows), plus
`py companion\test_desktop.py` for the Windows app.

## Building the Windows app
```
py -m pip install -r windows\requirements.txt
winget install JRSoftware.InnoSetup      # for the installer only
.\windows\build.ps1                      # dist\Brag\Brag.exe and dist\BragSetup.exe
```
`py companion\desktop.py` runs the app from source without building. Point it at a `fakewow.py` folder to try it
without WoW. The release workflow builds the installer with the same script on a Windows runner.

## Releasing to CurseForge
Pushing to `main` runs the tests. If the `## Version:` in `Brag/Brag.toc` is new (there's no `v<version>` tag yet),
GitHub Actions zips `Brag/`, uploads it to CurseForge as a release for the game version that matches `## Interface:`
(16001 → 1.60.1), then tags it and creates a GitHub release with that zip, `BragSetup.exe` and the commit list as changelog.
Pushes that don't bump the version only run the tests.

One-time setup:
```
gh secret set CF_API_TOKEN      # token from https://legacy.curseforge.com/account/api-tokens
gh variable set CF_PROJECT_ID   # numeric id from "About Project" on the CurseForge page
```
Without them the workflow still makes the GitHub release and skips CurseForge with a warning. To retry a failed upload: Actions → Test and release → Run workflow.

## Credits
The companion page's look is ported from [warcraftcn/ui](https://github.com/TheOrcDev/warcraftcn-ui) (MIT); its textures
and the [Cinzel](https://github.com/NDISCOVER/Cinzel) font (SIL OFL) are bundled in `companion/assets`, licenses in
`companion/assets/CREDITS.md`.
