#!/usr/bin/env python3
"""Post every new WoW screenshot to a Discord webhook.

Usage: DISCORD_WEBHOOK=https://discord.com/api/webhooks/... python3 watch.py "<WoW>/_forever_/Screenshots"
"""
import os, subprocess, sys, time

webhook = os.environ["DISCORD_WEBHOOK"]
folder = sys.argv[1]
seen = set(os.listdir(folder))
print(f"Watching {folder} (Ctrl+C to stop)")

while True:
    time.sleep(2)
    for name in sorted(set(os.listdir(folder)) - seen):
        seen.add(name)
        if not name.lower().endswith((".jpg", ".png")):
            continue
        time.sleep(1)  # let WoW finish writing the file
        r = subprocess.run(["curl", "-sSf", "-F", f"file=@{os.path.join(folder, name)}", webhook])
        print(("posted " if r.returncode == 0 else "FAILED ") + name)
