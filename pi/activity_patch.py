#!/usr/bin/env python3
"""
Patch main.c to support activity-based profile filenames.
Usage: ./gaitguard record walking [weights.bin]
Saves/loads profile_walking.bin instead of profile.bin
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "src/main.c"
data = open(path).read()
changes = 0

# 1. Replace the static PROFILE_PATH define with a char array
old = '#define PROFILE_PATH "profile.bin"'
new = 'static char profile_path[256] = "profile.bin";'
if old in data:
    data = data.replace(old, new, 1)
    changes += 1
    print("Patched PROFILE_PATH → dynamic profile_path")

# 2. Replace all PROFILE_PATH usages with profile_path
for old_ref, new_ref in [("PROFILE_PATH", "profile_path")]:
    count = data.count(old_ref)
    if count > 0:
        data = data.replace(old_ref, new_ref)
        changes += 1
        print(f"Replaced {count} references to {old_ref}")

# 3. Patch argv parsing: argv[2] = activity, argv[3] = weights
old_argv = '''    if (argc >= 3) weights_path = argv[2];'''
new_argv = '''    /* argv[2] = activity type (walking, running, jumping, stairs) */
    const char *activity = "walking";
    if (argc >= 3) activity = argv[2];
    if (argc >= 4) weights_path = argv[3];

    /* Build profile filename from activity: profile_walking.bin, etc. */
    snprintf(profile_path, sizeof(profile_path), "profile_%s.bin", activity);
    printf("[Main] Activity: %s  Profile: %s\\n", activity, profile_path);'''

if old_argv in data:
    data = data.replace(old_argv, new_argv, 1)
    changes += 1
    print("Patched argv parsing for activity")

# 4. Update usage message
old_usage = '''        fprintf(stderr, "  %s record [weights.bin]   — Record healthy gait\\n", argv[0]);
        fprintf(stderr, "  %s test   [weights.bin]   — Test patient gait\\n", argv[0]);'''
new_usage = '''        fprintf(stderr, "  %s record [activity] [weights.bin]  — Record healthy gait\\n", argv[0]);
        fprintf(stderr, "  %s test   [activity] [weights.bin]  — Test patient gait\\n", argv[0]);'''
if old_usage in data:
    data = data.replace(old_usage, new_usage, 1)
    changes += 1
    print("Patched usage message")

open(path, "w").write(data)
print(f"Done — {changes} patches applied. Rebuild with make")
