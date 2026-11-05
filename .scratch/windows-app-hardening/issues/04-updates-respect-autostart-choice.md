# 04: Updates respect the player's "Start with Windows" choice

**What to build:** Installing a newer BragSetup.exe never turns "Start with Windows" back on after the player turned it off.

Today the installer's "Start Brag when Windows starts" task is ticked by default and the installer remembers the previous install's task choices, so an update re-creates the startup entry even when the player switched it off from the tray menu afterwards. The tray menu and the installer write the same startup entry, but its name and the single-instance mutex name are typed separately in the app and in the installer script.

After this ticket:
- On an update, the installer's autostart choice reflects the current state (startup entry present or not), not the choice made at first install. A first install still offers it ticked.
- Uninstalling still removes the startup entry.
- The startup-entry name and the mutex name are defined once on the app side, with a comment pairing each to the installer script (the installer can't import them).

Source: Spec axis of the code review, finding (c)1; Standards smell 8.

**Blocked by:** 03 (One place says what state Brag is in)

**Status:** ready-for-agent

- [ ] Manual check: install with autostart on, turn it off in the tray, install the same or a newer BragSetup.exe: autostart stays off (the tray menu shows it unticked, and Brag doesn't start at login)
- [ ] Manual check: a first install on a clean machine offers autostart ticked and it works
- [ ] Uninstall removes the startup entry whether it was set by the installer or the tray
- [ ] The app side has a single definition of each shared name
