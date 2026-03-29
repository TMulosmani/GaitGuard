#!/usr/bin/env python3
"""
Patch gaitguard.c to remap IMU axes based on actual sensor mounting.

Sensor mounting (as of 2026-03-29):
  - Thigh (MPU-6050 @ 0x68): mounted on outer right thigh, flat against leg
    Gravity axis: aY (+0.93g when standing) → Y points UP
    Sagittal forward: aX
    Sagittal gyro: gX
    Angle formula: atan2(ax, ay)

  - Shin (MPU-6050 @ 0x69): mounted on outer right shin, flat against leg
    Gravity axis: aY (-0.96g when standing) → Y points DOWN
    Sagittal forward: aX
    Sagittal gyro: gX
    Angle formula: atan2(ax, -ay)  [negate because Y points down]

  - Foot (QMI8658C on ESP32-S3): mounted flat on top of foot
    Gravity axis: aZ (-0.40g, weak — sensor may have scaling issue)
    Sagittal forward: aX
    Sagittal gyro: gX
    Angle formula: atan2(ax, -az)
    Note: foot sensor has large gyro bias (~-28, +22 deg/s on gx, gy)

  For stride detection (conditions_met):
    - Instead of checking foot.az ≈ 1g (which assumes Z=down),
      check that total accel magnitude ≈ 1g (axis-independent)
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "src/gaitguard.c"
data = open(path).read()

# 1. Patch ac_update to use correct axes per sensor
old_ac = '''void ac_update(AngleComputer *ac, const SensorPacket *pkt, float *knee, float *ankle) {
    float ta = cf_update(&ac->cf_thigh, pkt->thigh.gx,
                         accel_to_angle(pkt->thigh.ax, pkt->thigh.az));
    float sa = cf_update(&ac->cf_shin, pkt->shin.gx,
                         accel_to_angle(pkt->shin.ax, pkt->shin.az));
    float fa = cf_update(&ac->cf_foot, pkt->foot.gx,
                         accel_to_angle(pkt->foot.ax, pkt->foot.az));'''

new_ac = '''void ac_update(AngleComputer *ac, const SensorPacket *pkt, float *knee, float *ankle) {
    /*
     * AXIS REMAPPING — sensors are not mounted with Z-down.
     * Thigh: gravity on +aY (Y points up)   → atan2(ax, ay)
     * Shin:  gravity on -aY (Y points down)  → atan2(ax, -ay)
     * Foot:  gravity on -aZ (Z points up-ish)→ atan2(ax, -az)
     * All three use gX for sagittal-plane gyro.
     */
    float ta = cf_update(&ac->cf_thigh, pkt->thigh.gx,
                         accel_to_angle(pkt->thigh.ax, pkt->thigh.ay));
    float sa = cf_update(&ac->cf_shin, pkt->shin.gx,
                         accel_to_angle(pkt->shin.ax, -pkt->shin.ay));
    float fa = cf_update(&ac->cf_foot, pkt->foot.gx,
                         accel_to_angle(pkt->foot.ax, -pkt->foot.az));'''

if old_ac in data:
    data = data.replace(old_ac, new_ac, 1)
    print("Patched ac_update")
else:
    print("WARNING: Could not find ac_update to patch")

# 2. Patch conditions_met to use axis-independent check
old_cond = '''static int conditions_met(const SensorPacket *pkt, float knee_deg) {
    float gx = pkt->foot.gx, gy = pkt->foot.gy, gz = pkt->foot.gz;
    float gyro_mag = sqrtf(gx*gx + gy*gy + gz*gz);
    float az_err = fabsf(fabsf(pkt->foot.az) - 1.0f);
    return (gyro_mag < OMEGA_THRESH_DPS &&
            az_err < ACCEL_Z_TOL_G &&
            fabsf(knee_deg) < KNEE_NEAR_ZERO_DEG);
}'''

new_cond = '''static int conditions_met(const SensorPacket *pkt, float knee_deg) {
    /*
     * AXIS-INDEPENDENT stride boundary detection.
     * Instead of checking foot.az ≈ 1g (assumes Z=down), we check that
     * the total accel magnitude ≈ 1g (foot is stationary on ground).
     * This works regardless of how the sensor is mounted.
     */
    float gx = pkt->foot.gx, gy = pkt->foot.gy, gz = pkt->foot.gz;
    float gyro_mag = sqrtf(gx*gx + gy*gy + gz*gz);
    float ax = pkt->foot.ax, ay = pkt->foot.ay, az = pkt->foot.az;
    float accel_mag = sqrtf(ax*ax + ay*ay + az*az);
    float mag_err = fabsf(accel_mag - 1.0f);
    return (gyro_mag < OMEGA_THRESH_DPS &&
            mag_err < ACCEL_Z_TOL_G &&
            fabsf(knee_deg) < KNEE_NEAR_ZERO_DEG);
}'''

if old_cond in data:
    data = data.replace(old_cond, new_cond, 1)
    print("Patched conditions_met")
else:
    print("WARNING: Could not find conditions_met to patch")

open(path, "w").write(data)
print("Done — rebuild with make")
