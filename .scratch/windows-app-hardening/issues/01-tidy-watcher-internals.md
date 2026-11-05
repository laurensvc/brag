# 01: Tidy the watcher's internals

**What to build:** A behaviour-preserving prefactor of the companion core, so the next two tickets are small changes. Nothing a player sees changes.

- The watcher's per-pass state ("which Screenshots folder, which screenshots were already seen, when old history was last cleaned up") becomes a small named type instead of an anonymous tuple rebuilt in several places. Give the single-pass function a name that says what it does.
- Repeated pieces get one home each: the path to a WoW folder's Screenshots folder, the "where are the bundled page files" lookup (source checkout vs. the packaged Windows app), the "1 screenshot / 2 screenshots" wording, and the "serve a file from a known folder, refusing anything not listed there" logic shared by the page's assets and the screenshot images.
- Names say what they hold: the tray app's "last failed post" (today a string named like a yes/no flag), the folder-dialog constant that only gets set at startup, the "already warned about a missing webhook" flag stored on a function, and the icon colour stashed on the tray library's object.
- Where new core code reads module-level state (current WoW folder, paused flag, listeners), prefer passing it in the way the older posting code takes its dependencies, if that keeps the tests simpler; don't force it where it doesn't.

Source: the Standards axis of the code review of the Windows tray app (smells 4, 5, 6, 7).

**Blocked by:** None (can start immediately). Prerequisite: the Windows tray app work is committed.

**Status:** ready-for-agent

- [ ] The watcher's per-pass state is a named type; no anonymous `(folder, seen, cleaned)` tuples remain
- [ ] Each duplicated piece listed above exists once and is reused
- [ ] The four unclear names above are renamed or restructured
- [ ] No behaviour change: all three test suites pass unchanged (or with only renames), and the CLI companion and the tray app start and post as before
