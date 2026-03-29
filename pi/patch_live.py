#!/usr/bin/env python3
"""Patch main.c to add "live":true to IMU JSON output."""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "src/main.c"
data = open(path).read()

old = '  "ankle":%.2f\\n"'
new = '  "ankle":%.2f,\\n  "live":true\\n"'

if old not in data:
    # Try the escaped version
    old = '  \\"ankle\\":%.2f\\n"'
    new = '  \\"ankle\\":%.2f,\\n  \\"live\\":true\\n"'

if old in data:
    data = data.replace(old, new, 1)
    open(path, "w").write(data)
    print("Patched OK")
else:
    print("Could not find target string. Current ankle lines:")
    for i, line in enumerate(data.split("\n")):
        if "ankle" in line:
            print(f"  {i+1}: {line}")
