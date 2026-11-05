# 07: Works on PCs without WebView2

**What to build:** A player whose Windows lacks the Microsoft Edge WebView2 runtime (some Windows 10 machines) still gets a working Brag window, or a clear way to get one, instead of a Brag that sits in the tray with no window.

The app window is an Edge WebView2 view. Windows 11 always has the runtime; older or locked-down Windows 10 installs may not, and today nothing checks.

After this ticket, either (implementer's choice, note which in the README):
- the installer detects the missing runtime and offers to download Microsoft's small WebView2 bootstrapper, or
- Brag detects at startup that the window can't open, tells the player once, and opens the same page in their default browser instead (the tray keeps working, and "Open Brag" opens the browser).

Source: Spec axis of the code review, finding (a), WebView2.

**Blocked by:** 06 (A release can't upload to CurseForge twice)

**Status:** ready-for-agent

- [ ] Without the WebView2 runtime, the player ends up with a working settings page (window or browser) and a message explaining what happened
- [ ] With the runtime present, nothing changes
- [ ] The README's Windows section mentions WebView2 and what happens without it
- [ ] Manual check documented in the ticket's PR/commit (how it was simulated)
