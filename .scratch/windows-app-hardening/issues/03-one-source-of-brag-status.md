# 03: One place says what state Brag is in

**What to build:** The tray tooltip/icon and the page's notice always agree on Brag's state, because both come from one answer the companion gives.

Today two things are stringly typed and duplicated:
- A post result is a single string like "posted after 1 retry", "failed: webhook was deleted (HTTP 404)" or "skipped: paused", and the tray app and the page each pick it apart (prefix checks, splitting on the first space or colon) to decide colours and notifications.
- "What state is Brag in" (no WoW folder, no Brag settings file yet, paused, last post failed, no webhook, turned off in game, all good) is worked out separately by the tray and by the page, in different orders with different wording.

After this ticket:
- A post result carries a kind (posted / failed / skipped) and a human reason. The post log keeps reading older entries that only have the combined string.
- The companion exposes one status (kind + message) in priority order. The tray's icon colour and tooltip and the page's header notice both use it. The page keeps colouring screenshot and log entries by result kind without parsing text.

Source: Standards axis of the code review, smells 1, 2 and 3.

**Blocked by:** 02 (The watcher never dies silently)

**Status:** ready-for-agent

- [ ] Post results have a kind and a reason; nothing parses the kind back out of the text
- [ ] An existing post log written before this change still shows the right status and colour for old screenshots
- [ ] One status function drives both the tray (colour + tooltip) and the page's notice; tests cover each state and the priority order
- [ ] Screenshot tiles and log lines are still coloured posted / failed / skipped
- [ ] All existing tests pass
