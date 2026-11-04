**Brag** shows a big banner and takes a screenshot whenever you:

- level up
- turn in a quest
- loot a good item (you pick the minimum quality)

Type **/brag** to open the settings: turn each event on or off, paste your Discord webhook and send a test post.

The companion also gives you a page in your browser to change settings, browse past screenshots and see your Brag history, without starting WoW.

**Posting to Discord needs a small companion script.** WoW addons can't access the internet, so the addon only takes the screenshot. The companion script runs on your PC, watches your Screenshots folder and uploads each new screenshot to a Discord webhook within a few seconds. Setup steps are in the project's README.

Notes:
- Screenshots you take yourself (Print Screen) are posted too while the companion runs.
- Without the companion, Brag still takes the screenshots; nothing gets posted.

---

Source code: https://github.com/laurensvc/brag
