# 07: Works on PCs without WebView2

**What to build:** A player whose Windows lacks the Microsoft Edge WebView2 runtime (some Windows 10 machines) still gets a working Brag window, or a clear way to get one, instead of a Brag that sits in the tray with no window.

The app window is an Edge WebView2 view. Windows 11 always has the runtime; older or locked-down Windows 10 installs may not, and today nothing checks.

After this ticket, either (implementer's choice, note which in the README):
- the installer detects the missing runtime and offers to download Microsoft's small WebView2 bootstrapper, or
- Brag detects at startup that the window can't open, tells the player once, and opens the same page in their default browser instead (the tray keeps working, and "Open Brag" opens the browser).

Source: Spec axis of the code review, finding (a), WebView2.

**Blocked by:** 06 (A release can't upload to CurseForge twice)

**Status:** done

- [x] Without the WebView2 runtime, the player ends up with a working settings page (window or browser) and a message explaining what happened
- [x] With the runtime present, nothing changes
- [x] The README's Windows section mentions WebView2 and what happens without it
- [x] Manual check documented in the ticket's PR/commit (how it was simulated)

**Done:** chose the browser fallback. Brag checks the WebView2 runtime (Microsoft's registry check) at startup; without it, it says so once per PC and runs from the tray with the page in the browser. The WoW folder card now has a text field that saves through POST /api/folder, so the folder can be set without the window. Simulated with `--browser` (same code path minus the one-time message, which is unit-tested).
