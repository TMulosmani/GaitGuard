Inspiration

  One of our team members has spent years working at a rehabilitation center and has watched this problem play out over and over. Patients leave the clinic motivated, but at home there is no
  one to tell them if they are doing the exercise right or wrong. Compliance drops, recovery stalls, and therapists only find out at the next visit. That gap between intention and feedback is
   what inspired us to build GaitGuard.

  What it does

  GaitGuard is a wearable system that turns any rehab exercise into a guided session, even when the therapist is not in the room.

  It starts with the therapist. They strap on the sensors and perform the target movement a few times. The system captures that motion and trains a personalized digital twin of what correct
  movement looks like for this specific patient, not a textbook average.

  From that point on, every rep the patient performs is compared against their own baseline in real time. If the movement matches, nothing happens. If it drifts, a haptic motor vibrates
  immediately with a pattern that tells the patient what to fix. No screen required. No interpretation needed.

  This is not limited to walking. The system can be calibrated to knee bends, stair steps, ankle exercises, and a wide range of physical therapy movements. Patients take the device home and
  train with real-time correction on their own.

  How we built it

  Hardware. The system has three sensor units, all housed in custom 3D printed enclosures designed in SolidWorks and printed in PLA on a Bambu X1C. The main unit straps to the shin and
  contains an ESP32, an MPU-6050 IMU, a 3.7V 300mAh LiPo battery with charger, and a haptic vibration motor. A second MPU-6050 in its own enclosure straps to the ankle, connected to the main
  unit through protected wire sheathing. The third unit is an ESP32 with a 1.69" touch display and built-in IMU that straps to the foot, powered by its own battery. All units attach with
  Velcro for quick application and removal. A Raspberry Pi 5 serves as the central processing hub.

  Signal processing. Each ESP32 samples its IMU at 50 Hz and streams raw accelerometer and gyroscope data over WiFi to the Raspberry Pi. A complementary filter (α = 0.98) fuses those signals
  into stable joint angle estimates for the shin, ankle, and foot, correcting for gyroscope drift in real time.

  Calibration pipeline. During setup the therapist performs several clean repetitions of the target movement. Each rep is automatically segmented, passed through a 4th-order Butterworth
  low-pass filter at 6 Hz to remove noise, and time-normalized to 100 data points so reps of different speeds can be compared fairly.

  Digital twin model. The core of the system is a two-layer stacked LSTM neural network built in PyTorch. Given the first portion of a new rep, the model predicts what the correct remainder
  of that movement should look like. It is trained entirely on the patient's own calibration data. The deviation between the predicted trajectory and the actual sensor readings is computed at
   each time step and condensed into a Gait Health Score (GHS) from 0 to 100. When the score drops below a clinical threshold, the system sends a command back to the ESP32 and the haptic
  motor fires with a vibration pattern corresponding to the specific type of error.

  Dashboard. Session data is visualized through a React and TypeScript web dashboard showing a live overlay of observed movement against the digital twin, a per-rep GHS trend chart, and a
  deviation heatmap. At the end of each session the system generates a PDF report containing all charts, a per-rep summary table, and a haptic trigger log that the therapist can review
  remotely.

  Challenges we ran into

  The biggest challenge was making the LSTM model produce accurate predictions from only a handful of calibration reps. With so little training data, the model was prone to learning noise
  rather than the actual movement pattern. Getting this right required careful signal filtering, strict time normalization, and deliberate augmentation of the small calibration set.

  Beyond the model, sensor drift across three independent IMUs over a full session introduced subtle errors that compounded over time. We also had to solve reliable synchronization of data
  streams from multiple ESP32s over WiFi. Dropped packets or timestamp mismatches between the shin, ankle, and foot sensors would corrupt the joint angle calculations downstream, so we built
  in sequence numbering and interpolation to handle gaps cleanly.

  Accomplishments that we're proud of

  The accomplishment we are most proud of is the personalized digital twin. By comparing patients against their own therapist-prescribed movement rather than a population average, individual
  variation stops being a false positive. A movement that is perfectly normal for one patient is not incorrectly flagged just because it does not match a generic reference curve.

  We are also proud of the hardware. The number of components packed into each enclosure is significant, and the press-fit enclosures came out right on the first print. The form factor is
  practical, comfortable, and something a patient could realistically wear during a home exercise session.

  Getting the full pipeline running end to end, from raw IMU data all the way to a haptic buzz on the patient's leg, with latency low enough to feel immediate during a rep, was something we
  were not sure we could pull off in the time we had. We did.

  What we learned

  The most surprising lesson was that sensor fusion and drift correction matter just as much as the model itself. The machine learning is only as good as the data going into it, and getting clean, stable joint angles from cheap IMUs required more engineering effort than training the LSTM.

  We also learned that usability drives everything. Simple, distinct haptic patterns were far more effective than asking patients to watch a screen or interpret a score while exercising. The feedback has to be immediate, obvious, and require zero thought from the patient.

  Finally, we saw firsthand why personalization matters in rehabilitation. Population averages can misclassify normal individual variation as error. What looks like a deviation for one patient is perfectly correct movement for another. Building the system around each patient's own baseline eliminated that problem entirely.

  What's next for GaitGuard

  The next step is clinical validation through studies with physical therapists and rehab clinics, measuring patient outcomes against standard unsupervised home exercise programs. We want to move model inference fully on-device so the system works without any connected computer, and build a therapist-facing dashboard for monitoring patient progress between visits with session reports, score trends, and alerts when a patient starts struggling. Longer term, expanding the haptic pattern library and supporting a broader set of exercises would open GaitGuard up to a much wider range of outpatient rehabilitation.