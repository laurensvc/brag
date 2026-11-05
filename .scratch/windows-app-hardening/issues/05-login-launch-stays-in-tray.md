# 05: Starting at login stays in the tray

**What to build:** When Windows starts Brag at login (the "start in the tray" launch) and Brag is already running, nothing pops up. A launch by the player (Start menu, desktop shortcut, double-click) while Brag runs still brings the existing window to the front.

Today any second launch asks the running Brag to show its window, including the tray-only launch, so the window can pop up at login (for example when Brag was already started by the installer's "Open Brag" or by hand before the startup entry ran).

Source: Spec axis of the code review, finding (c)5.

**Blocked by:** 04 (Updates respect the player's "Start with Windows" choice)

**Status:** done

- [x] A tray-only launch while Brag is running exits quietly without showing the window
- [x] A normal launch while Brag is running still shows and focuses the existing window
- [x] A tray-only launch when Brag is not running starts it hidden in the tray, as today (and shows the window if no WoW folder is set yet)
- [x] Covered by a test of the "already running" decision, plus a manual check with the built Brag.exe
