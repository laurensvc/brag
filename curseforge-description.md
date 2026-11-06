# Brag: share your best (and worst) WoW Forever moments on Discord, automatically

You hit level 60, finally get that epic drop, or wipe your guild's first Ragnaros kill into the history books. With **Brag**, your Discord server sees it within seconds: a screenshot of the moment plus a caption saying who did what, where. You don't have to alt-tab, crop or paste anything.

Brag is made for guilds and groups of friends who share a Discord server and want a running feed of each other's progress: dings, loot, boss kills and the occasional embarrassing death.

## ⚠️ You also need the free Brag app to post to Discord

**Installing this addon from CurseForge is only half of Brag.** WoW addons can't access the internet (that's a rule of the game), so the addon only shows the banner and takes the screenshot. A small free **companion app** on your PC posts the screenshots to Discord. **Without the app, nothing gets posted.**

### 👉 [Download BragSetup.exe (Windows)](https://github.com/laurensvc/brag/releases/latest/download/BragSetup.exe)

Mac or Linux: the companion runs as a small Python script, see the [GitHub README](https://github.com/laurensvc/brag).

Until Brag sees the app, it reminds you at login with the download link (or type **/brag** and click **Get the app**).

### Setup in 4 steps (Windows)

1. Download and run **BragSetup.exe** (link above). You don't need admin rights. Windows may warn about an unknown publisher: click **More info**, then **Run anyway**.
2. Brag finds your WoW folder and installs the addon.
3. In Discord, go to **Server Settings > Integrations > Webhooks > New Webhook**, copy the URL, and paste it into Brag. Click **Send test message** to check it.
4. Play. Brag posts while you play.

---

## What Brag does in game

Brag watches for five kinds of moments. When one happens, it shows a **big raid-warning style banner** in the middle of your screen and **takes a screenshot** a split second later, so the banner is in the picture.

| Moment | When it triggers | Banner you see |
|---|---|---|
| **Level up** | Every time you ding | *Level 42!* |
| **Quest turn-in** | When you hand in a quest | *Quest complete: Bounty on Murlocs* |
| **Big loot** | When you loot an item of your chosen quality or better (Uncommon, Rare, Epic or Legendary; Epic by default). Quest rewards and mail count too | *Big drop: [Krol Blade]* |
| **Boss kill** | When your group defeats a dungeon or raid boss. Wipes are never posted | *Boss defeated: Onyxia* |
| **Death** | When you die. Brag also works out **what killed you**: a mob, a mob's spell, or falling, lava, drowning and so on | *Died to Hogger's Fireball in Elwynn Forest* |

A few more details:

- If a quest turn-in also levels you up, you get **two separate screenshots**, one for each moment.
- Every moment can be **switched on or off** separately, so you can share your loot but keep your deaths private, or the other way around.
- Brag keeps an in-game **history** of your last 500 moments, which the companion app shows you.
- While Brag takes a screenshot, a thin strip of small black and white blocks flashes in the top-left corner for a moment. This strip carries the details (your name, level, zone, item and so on) to the companion app, which **crops it off** before posting. It never shows up on Discord.
- Brag does nothing in combat or in your interface apart from the banner (and, until it sees the app, a reminder at login). It doesn't change your action bars, chat or unit frames, and it only listens to a few game events.

## What your Discord server sees

Each moment becomes a Discord post with the screenshot and a caption with your character's name, level, class and zone:

> 🎉 **Thrall** reached **level 42**! · Shaman · Orgrimmar
>
> 📜 **Jaina Proudmoore** completed **The Missing Diplomat** · Level 41 Mage · Theramore Isle
>
> 💎 **Thrall** looted **[Thunderfury, Blessed Blade of the Windseeker]** (Legendary) · Level 60 Shaman · Molten Core
>
> ⚔️ **Thrall** defeated **Ragnaros**! · Level 60 Shaman · Molten Core
>
> 💀 **Thrall** died to **Hogger's Fireball** · Level 12 Shaman · Elwynn Forest

### Funny captions (on by default)

To keep the feed fun to read, Brag picks a random joke line for each post from a large set per moment. For example:

> 🎉 Grats **Thrall** on level **42**! Sleep is for max level
>
> 💎 **Thrall** looted **[Krol Blade]** (Epic). Somewhere, a guildie is quietly crying
>
> 💀 **Hogger's Fireball** would like everyone to know they killed **Thrall**
>
> 💀 RIP **Thrall**. Cause of death: **Lava**

Prefer plain captions? One switch turns the jokes off.

## Settings in game: /brag

Type **/brag** to open the settings window:

- **Enabled**: turn Brag on or off completely.
- **Level ups, Quest turn-ins, Loot, Boss kills, Deaths**: a checkbox for each moment.
- **Loot quality**: click to choose the minimum quality: Uncommon, Rare, Epic or Legendary.
- **Discord webhook URL**: where your posts go (setting it in the companion app is easier).
- **Test post**: takes a test screenshot so you can check that everything works: *"Brag test from Thrall: if you can read this, you're all set!"*
- **Get the app**: shows the download link for the companion app (only while Brag hasn't seen the app yet).

## More about the companion app

**On Windows**, the companion is a tray app with an installer, **BragSetup.exe** (link above). It:

- **finds your WoW Forever folder** for you, or asks for it once;
- **installs and updates this addon for you**, so you don't have to copy any files by hand;
- walks you through **connecting Discord** with a setup checklist and a **Send test message** button;
- waits in the system tray next to the clock and posts each new screenshot **within a few seconds**;
- shows your **screenshots, your Brag history and a log of every post** in one window;
- can **pause posting** with one click, and can **start with Windows**;
- **retries** if Discord has a hiccup, and shows a Windows notification if a post really fails;
- shrinks big screenshots (1440p, 4K) to 1080p by default, so posts load fast on Discord;
- can optionally clean up old screenshots after a number of days.

**On Mac and Linux**, the same companion runs as a small Python script with the same setup page in your browser. The steps are in the GitHub README.

---

## Good to know

- **Screenshots you take yourself** (Print Screen) are posted too while the companion runs, without a caption. You can pause posting from the tray icon.
- **Your Discord link stays on your PC.** The companion only talks to Discord, and its settings page only listens on your own computer.
- **WoW Forever names**: posts use your character's full first and last name.
- **Is it safe?** The addon only uses WoW's own banner and screenshot functions. The companion only reads your Screenshots folder and the addon's saved settings, and never touches the game itself.

## Feedback and source code

Brag is free and open source. Bug reports, ideas and new funny captions are welcome on GitHub: https://github.com/laurensvc/brag
