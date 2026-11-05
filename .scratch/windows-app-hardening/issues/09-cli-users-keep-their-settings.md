# 09: Existing CLI users keep their settings

**What to build:** A player who ran the command-line companion before and now installs the Windows app keeps their posting settings (caption, retries, image size, JPEG quality, history days, deleting old screenshots) and sees the "posted" badges on their older screenshots.

The Windows app keeps its settings and post log in the player's app-data folder, while the command-line companion keeps them next to its script. Today nothing carries them over, so the app starts with default posting settings and older screenshots show no post status.

After this ticket:
- On its first run (no companion settings in app data yet), the app looks for the command-line companion's settings and post log and copies them over, then writes a line in the Log tab saying what it imported.
- It only ever copies (never moves or deletes), only once, and only where it can find them: next to the app when run from source, or a folder the player points it at. If it can't find them, it does nothing.
- Invalid or corrupt old settings fall back to defaults, as today.

Source: Spec axis of the code review, finding (a), settings migration.

**Blocked by:** 08 (The first run asks for the WoW folder)

**Status:** done

- [x] Test: old settings and post log present, app data empty: both are imported and a Log line says so
- [x] Test: app data already has settings: nothing is imported or overwritten
- [x] Test: corrupt old settings: defaults are used and the run doesn't fail
- [x] The originals are left untouched
