# 08: The first run asks for the WoW folder

**What to build:** On the first run, if Brag can't find the WoW Forever folder in the usual install places, the window opens with the folder dialog already showing, instead of waiting for the player to find the WoW folder card and click "Choose folder…".

- The dialog opens once the window is ready; cancelling it leaves the WoW folder card and the "Choose your WoW folder" notice, as today.
- Picking a folder that isn't WoW (no Interface or WTF inside, directly or in its _forever_ subfolder) shows the existing explanation and lets the player try again.
- If the window's bridge to the app never becomes ready, the player still sees how to choose the folder (the card or notice must not depend solely on that signal).
- Players whose folder was found automatically, or who already chose one, never see the dialog.

Source: Spec axis of the code review, finding (a), first-run folder picker.

**Blocked by:** 07 (Works on PCs without WebView2)

**Status:** ready-for-agent

- [ ] Fresh settings and no WoW in the usual places: the window opens with the folder dialog showing
- [ ] A WoW folder found automatically or saved earlier: no dialog
- [ ] Picking the install folder works (it finds _forever_ inside); picking an unrelated folder shows the explanation
- [ ] The WoW folder card is reachable even if the bridge-ready signal never arrives
