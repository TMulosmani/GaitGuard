#!/usr/bin/env python3
"""
Patch main.c to use remapped axes for calibration and live IMU display.
See axis_patch.py for full mounting documentation.
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "src/main.c"
data = open(path).read()

# 1. Patch live foot angle display
old = "live_foot_angle = accel_to_angle(live_foot_raw.ax, live_foot_raw.az);"
new = "live_foot_angle = accel_to_angle(live_foot_raw.ax, -live_foot_raw.az); /* foot: gravity on -aZ */"
if old in data:
    data = data.replace(old, new, 1)
    print("Patched live_foot_angle")
else:
    print("WARNING: Could not find live_foot_angle")

# 2. Patch calibration axis calls
old_calib = """pipeline.calib_thigh[i] = accel_to_angle(pkt.thigh.ax, pkt.thigh.az);
                    pipeline.calib_shin[i]  = accel_to_angle(pkt.shin.ax, pkt.shin.az);
                    pipeline.calib_foot[i]  = accel_to_angle(pkt.foot.ax, pkt.foot.az);"""

new_calib = """/* AXIS REMAPPING — see axis_patch.py for mounting docs */
                    pipeline.calib_thigh[i] = accel_to_angle(pkt.thigh.ax, pkt.thigh.ay);
                    pipeline.calib_shin[i]  = accel_to_angle(pkt.shin.ax, -pkt.shin.ay);
                    pipeline.calib_foot[i]  = accel_to_angle(pkt.foot.ax, -pkt.foot.az);"""

if old_calib in data:
    data = data.replace(old_calib, new_calib, 1)
    print("Patched calibration")
else:
    print("WARNING: Could not find calibration block")

open(path, "w").write(data)
print("Done — rebuild with make")
