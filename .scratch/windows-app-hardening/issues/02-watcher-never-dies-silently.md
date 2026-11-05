# 02: The watcher never dies silently

**What to build:** Brag keeps posting no matter what goes wrong while handling one screenshot, and says so when something does.

Today the watcher only survives file-system errors. Any other error in a pass (a listener such as the tray notification failing, a bad value reaching cleanup) ends the watcher thread silently: the tray still says "watching", but nothing is ever posted again until Brag restarts.

Also, a pass reads the current WoW folder several times. If the player switches folders mid-pass, a screenshot found in the old folder can be handled against the new one and logged as a false "failed".

After this ticket:
- Any error during a pass is caught, written to the Log tab and the log file (with enough detail to debug), the tray icon turns red, and the next pass runs normally.
- A broken listener can't stop the other listeners or the watcher.
- Each pass reads the WoW folder once and uses that value throughout, so a folder switch takes effect cleanly on the next pass.

Source: Spec axis of the code review, findings (c)2 and (c)3.

**Blocked by:** 01 (Tidy the watcher's internals)

**Status:** ready-for-agent

- [ ] A test with a listener that raises shows the watcher still handles the next screenshot, and the error appears in the companion's log
- [ ] A test that switches the WoW folder during a pass shows no screenshot is handled against the wrong folder and no false "failed" is logged
- [ ] In the tray app, an error in a pass turns the icon red with the error in its tooltip; the next successful post clears it
- [ ] All existing tests pass
