 
## Step 1: Record Healthy Gait (5 min)
1. Strap sensors on — thigh on outer right thigh, shin on outer right shin, foot flat on top of foot
2. Run: `ssh qnxuser@172.20.10.5 "cd ~/GaitGuard/pi && ./start.sh record"`
3. Stand completely still for 2 seconds (calibration happens automatically)
4. Walk normally back and forth for 60 seconds — pipeline needs 20+ strides
5. Stop: `ssh qnxuser@172.20.10.5 "slay -f gaitguard"`
6. Verify profile saved: `ssh qnxuser@172.20.10.5 "ls -la ~/GaitGuard/pi/profile.bin"`

## Step 2: Test Mode — See Haptics Fire (5 min)
1. Run: `ssh qnxuser@172.20.10.5 "cd ~/GaitGuard/pi && ./start.sh test"`
2. Stand still 2 seconds (re-calibrates)
3. Walk with an exaggerated limp — stiff knee, dragging foot
4. Watch dashboard for GHS scores dropping + haptic motor buzzing
5. Walk normally — scores should be high, no haptics

## Step 3: Demo Loop (5 min)
1. Keep test mode running
2. Walk normally → high GHS, green, no haptics
3. Walk with limp → low GHS, red, haptic buzzes
4. Dashboard at http://172.20.10.5:8080 shows everything live
5. Show the 3D leg visualization reacting in real-time

## Haptic Patterns
- **Two short pulses** — insufficient knee extension at heel strike
- **One long buzz** — poor foot clearance during swing
- **Three short pulses** — general high deviation

## Quick Commands
- Start record: `ssh qnxuser@172.20.10.5 "cd ~/GaitGuard/pi && ./start.sh record"`
- Start test: `ssh qnxuser@172.20.10.5 "cd ~/GaitGuard/pi && ./start.sh test"`
- Stop pipeline: `ssh qnxuser@172.20.10.5 "slay -f gaitguard"`
- Check logs: `ssh qnxuser@172.20.10.5 "cat /tmp/gaitguard_pipeline.log"`
