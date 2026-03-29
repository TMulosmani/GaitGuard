/*
 * GaitGuard — ESP32 #1: Thigh/Shin IMU + Haptic Motor
 *
 * Reads two MPU-6050 IMUs over I2C, sends raw 6-axis data to the
 * Raspberry Pi via WiFi UDP at 50 Hz. Listens for haptic commands
 * from the Pi and drives a vibration motor accordingly.
 *
 * Packet format (27 bytes):
 *   [0]      device_id   (0x01)
 *   [1..2]   seq         (uint16, big-endian)
 *   [3..14]  thigh IMU   (ax,ay,az,gx,gy,gz — 6 × int16 BE)
 *   [15..26] shin IMU    (ax,ay,az,gx,gy,gz — 6 × int16 BE)
 *
 * Haptic command format (incoming, 2 bytes):
 *   [0] pattern  (0=none, 1=TWO_SHORT, 2=ONE_LONG, 3=THREE_SHORT)
 *   [1] intensity (0-255, reserved for future use)
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include "../config.h"

// --- I2C pins (ESP32 default) ---
#define I2C_SDA 21
#define I2C_SCL 22

// --- MPU-6050 addresses ---
#define MPU_THIGH 0x68  // AD0 → GND  = 0x68
#define MPU_SHIN  0x69  // AD0 → 3.3V = 0x69

// --- Haptic motor pin ---
#define HAPTIC_PIN 19

// --- Haptic patterns ---
#define PAT_NONE        0
#define PAT_TWO_SHORT   1
#define PAT_ONE_LONG    2
#define PAT_THREE_SHORT 3

// --- Globals ---
WiFiUDP udpOut;           // sending IMU data
WiFiUDP udpIn;            // receiving haptic commands
uint16_t seqNum = 0;
uint8_t txBuf[27];
unsigned long lastSampleTime = 0;

// Haptic state machine
volatile uint8_t hapticPattern = PAT_NONE;
unsigned long hapticStartTime = 0;
uint8_t hapticStep = 0;
bool hapticActive = false;

// --------------------------------------------------------------------
// MPU-6050 helpers
// --------------------------------------------------------------------

void mpuWakeup(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(0x6B);  // PWR_MGMT_1
  Wire.write(0x00);  // wake up
  Wire.endTransmission(true);
}

void mpuSetRange(uint8_t addr) {
  // Accel: ±4g (sensitivity 8192 LSB/g)
  Wire.beginTransmission(addr);
  Wire.write(0x1C);
  Wire.write(0x08);
  Wire.endTransmission(true);

  // Gyro: ±500°/s (sensitivity 65.5 LSB/°/s)
  Wire.beginTransmission(addr);
  Wire.write(0x1B);
  Wire.write(0x08);
  Wire.endTransmission(true);

  // DLPF: 44 Hz bandwidth (good for 50 Hz sampling)
  Wire.beginTransmission(addr);
  Wire.write(0x1A);
  Wire.write(0x03);
  Wire.endTransmission(true);
}

// Read 6 raw int16 values (ax, ay, az, gx, gy, gz)
void mpuRead(uint8_t addr, int16_t out[6]) {
  Wire.beginTransmission(addr);
  Wire.write(0x3B);  // ACCEL_XOUT_H
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)addr, (uint8_t)14, (uint8_t)true);

  out[0] = (Wire.read() << 8) | Wire.read();  // ax
  out[1] = (Wire.read() << 8) | Wire.read();  // ay
  out[2] = (Wire.read() << 8) | Wire.read();  // az
  Wire.read(); Wire.read();                     // skip temp
  out[3] = (Wire.read() << 8) | Wire.read();  // gx
  out[4] = (Wire.read() << 8) | Wire.read();  // gy
  out[5] = (Wire.read() << 8) | Wire.read();  // gz
}

// Pack 6 int16 values into buffer at offset (12 bytes, big-endian)
void packIMU(int16_t vals[6], uint8_t* buf, int offset) {
  for (int i = 0; i < 6; i++) {
    buf[offset + i * 2]     = (vals[i] >> 8) & 0xFF;
    buf[offset + i * 2 + 1] = vals[i] & 0xFF;
  }
}

// --------------------------------------------------------------------
// Haptic motor control
// --------------------------------------------------------------------

void startHaptic(uint8_t pattern) {
  hapticPattern = pattern;
  hapticStep = 0;
  hapticStartTime = millis();
  hapticActive = true;
}

void updateHaptic() {
  // Normal mode: HIGH=ON, LOW=OFF (MOSFET gate on GPIO)
  if (!hapticActive) return;

  unsigned long elapsed = millis() - hapticStartTime;

  switch (hapticPattern) {
    case PAT_TWO_SHORT:
      // buzz 100ms, off 80ms, buzz 100ms
      if (hapticStep == 0) {
        digitalWrite(HAPTIC_PIN, HIGH);
        if (elapsed >= 100) { hapticStep = 1; hapticStartTime = millis(); }
      } else if (hapticStep == 1) {
        digitalWrite(HAPTIC_PIN, LOW);
        if (elapsed >= 80) { hapticStep = 2; hapticStartTime = millis(); }
      } else if (hapticStep == 2) {
        digitalWrite(HAPTIC_PIN, HIGH);
        if (elapsed >= 100) { digitalWrite(HAPTIC_PIN, LOW); hapticActive = false; }
      }
      break;

    case PAT_ONE_LONG:
      // buzz 400ms
      digitalWrite(HAPTIC_PIN, HIGH);
      if (elapsed >= 400) { digitalWrite(HAPTIC_PIN, LOW); hapticActive = false; }
      break;

    case PAT_THREE_SHORT:
      // buzz 80ms, off 60ms, buzz 80ms, off 60ms, buzz 80ms
      if (hapticStep % 2 == 0) {
        digitalWrite(HAPTIC_PIN, HIGH);
        if (elapsed >= 80) { hapticStep++; hapticStartTime = millis(); }
      } else {
        digitalWrite(HAPTIC_PIN, LOW);
        if (hapticStep >= 5) { hapticActive = false; break; }
        if (elapsed >= 60) { hapticStep++; hapticStartTime = millis(); }
      }
      break;

    default:
      digitalWrite(HAPTIC_PIN, LOW);
      hapticActive = false;
      break;
  }
}

// --------------------------------------------------------------------
// WiFi connection
// --------------------------------------------------------------------

void connectWiFi() {
  Serial.printf("Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nConnected! IP: %s\n", WiFi.localIP().toString().c_str());
}

// --------------------------------------------------------------------
// Setup & Loop
// --------------------------------------------------------------------

void setup() {
  // FIRST THING: turn motor off before anything else
  pinMode(HAPTIC_PIN, OUTPUT);
  digitalWrite(HAPTIC_PIN, LOW);  // OFF

  Serial.begin(115200);
  delay(100);

  // I2C on GPIO 21 (SDA) / 22 (SCL)
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);  // 400 kHz fast mode
  mpuWakeup(MPU_THIGH);
  mpuWakeup(MPU_SHIN);
  mpuSetRange(MPU_THIGH);
  mpuSetRange(MPU_SHIN);
  Serial.println("MPU-6050 x2 initialized");

  // WiFi
  connectWiFi();

  // UDP sockets — use port 5003 for both sending and receiving
  udpOut.begin(PORT_HAPTIC_CMD);     // bind to 5003, also used for sending
  Serial.printf("UDP bound to port %d (send + receive haptic)\n", PORT_HAPTIC_CMD);

  // Pre-fill static header byte
  txBuf[0] = DEVICE_ID_THIGH_SHIN;

  lastSampleTime = millis();
}

void loop() {
  unsigned long now = millis();

  // --- 50 Hz IMU sampling & transmit ---
  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;

    int16_t thighData[6], shinData[6];
    mpuRead(MPU_THIGH, thighData);
    mpuRead(MPU_SHIN, shinData);

    // Pack packet
    txBuf[1] = (seqNum >> 8) & 0xFF;
    txBuf[2] = seqNum & 0xFF;
    packIMU(thighData, txBuf, 3);
    packIMU(shinData, txBuf, 15);

    // Send to Pi
    udpOut.beginPacket(PI_IP, PORT_IMU_THIGH_SHIN);
    udpOut.write(txBuf, 27);
    udpOut.endPacket();

    seqNum++;
  }

  // --- Check for incoming haptic commands ---
  int packetSize = udpOut.parsePacket();
  if (packetSize >= 1) {
    uint8_t cmdBuf[2] = {0, 0};
    udpOut.read(cmdBuf, min(packetSize, 2));
    uint8_t pattern = cmdBuf[0];
    if (pattern >= PAT_TWO_SHORT && pattern <= PAT_THREE_SHORT) {
      Serial.printf("Haptic cmd: pattern=%d\n", pattern);
      startHaptic(pattern);
    }
  }

  // --- Drive haptic motor state machine ---
  updateHaptic();
}
