/*
 * GaitGuard — ESP32-S3 #2: Foot IMU + Touch LCD Display
 * Board: Waveshare ESP32-S3-Touch-LCD-1.69
 *
 * Hardware:
 *   LCD:   ST7789V2, 240×280, SPI (MOSI=7, SCLK=6, CS=5, DC=4, RST=8, BL=15)
 *   IMU:   QMI8658C, I2C addr 0x6B (SDA=11, SCL=10)
 *   Touch: CST816T, I2C addr 0x15 (INT=14, RST=13)
 *
 * Sends foot IMU data to Pi via WiFi UDP at 50 Hz.
 * Receives display commands from Pi to show Gait Health Score.
 *
 * Packet format (15 bytes):
 *   [0]      device_id   (0x02)
 *   [1..2]   seq         (uint16, big-endian)
 *   [3..14]  foot IMU    (ax,ay,az,gx,gy,gz — 6 × int16 BE)
 *
 * Display command format (incoming, 6 bytes):
 *   [0]    command type   (1=score_update, 2=calibration, 3=session_summary)
 *   [1..2] ghs_score      (uint16 BE, score × 10)
 *   [3]    color           (0=green, 1=yellow, 2=red)
 *   [4]    state           (0=idle, 1=calibrating, 2=walking, 3=done)
 *   [5]    reserved
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <TFT_eSPI.h>
#include "../config.h"

// --- Board-specific pins ---
#define I2C_SDA  11
#define I2C_SCL  10
#define LCD_BL   15

// --- QMI8658C registers ---
#define QMI_ADDR          0x6B
#define QMI_WHO_AM_I      0x00   // should read 0x05
#define QMI_CTRL1         0x02   // sensor enable
#define QMI_CTRL2         0x03   // accel config
#define QMI_CTRL3         0x04   // gyro config
#define QMI_CTRL5         0x06   // low-pass filter
#define QMI_CTRL7         0x08   // enable accel + gyro
#define QMI_STATUSINT     0x2D
#define QMI_STATUS0       0x2E
#define QMI_AX_L          0x35   // accel data start (6 bytes: AX_L,AX_H,AY_L,AY_H,AZ_L,AZ_H)
#define QMI_GX_L          0x3B   // gyro data start  (6 bytes: GX_L,GX_H,GY_L,GY_H,GZ_L,GZ_H)

// --- Display command types ---
#define CMD_SCORE_UPDATE     1
#define CMD_CALIBRATION      2
#define CMD_SESSION_SUMMARY  3

// --- Color codes ---
#define COLOR_GREEN  0
#define COLOR_YELLOW 1
#define COLOR_RED    2

// --- State codes ---
#define STATE_IDLE        0
#define STATE_CALIBRATING 1
#define STATE_WALKING     2
#define STATE_DONE        3

// --- Globals ---
TFT_eSPI tft = TFT_eSPI();
WiFiUDP udpOut;
WiFiUDP udpIn;
uint16_t seqNum = 0;
uint8_t txBuf[15];
unsigned long lastSampleTime = 0;

// Display state
float displayScore = 0.0;
uint8_t displayColor = COLOR_GREEN;
uint8_t displayState = STATE_IDLE;
bool displayDirty = true;
unsigned long lastDisplayUpdate = 0;

// Scale factors for QMI8658C
// Accel: ±4g → 8192 LSB/g (same scale as MPU-6050 ±4g)
// Gyro:  ±512°/s → 64 LSB/(°/s)
float accelScale = 8192.0;
float gyroScale  = 64.0;

// TFT color mapping
uint16_t tftColors[] = {
  TFT_GREEN,
  TFT_YELLOW,
  TFT_RED
};

// --------------------------------------------------------------------
// QMI8658C IMU driver
// --------------------------------------------------------------------

void qmiWriteReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(QMI_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission(true);
}

uint8_t qmiReadReg(uint8_t reg) {
  Wire.beginTransmission(QMI_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)QMI_ADDR, (uint8_t)1);
  return Wire.read();
}

bool qmiInit() {
  // Check WHO_AM_I
  uint8_t id = qmiReadReg(QMI_WHO_AM_I);
  Serial.printf("QMI8658 WHO_AM_I: 0x%02X (expect 0x05)\n", id);
  if (id != 0x05) {
    Serial.println("ERROR: QMI8658 not found!");
    return false;
  }

  // Reset
  qmiWriteReg(QMI_CTRL1, 0x60);  // soft reset (bit 6+5)
  delay(20);
  // SPI/I2C auto-increment enable
  qmiWriteReg(QMI_CTRL1, 0x40);

  // Accel config: ±4g, ODR 113 Hz (closest to 50Hz output after filter)
  // CTRL2[6:4]=010 (±4g), CTRL2[3:0]=0100 (112.5 Hz ODR)
  qmiWriteReg(QMI_CTRL2, 0x24);

  // Gyro config: ±512°/s, ODR 113 Hz
  // CTRL3[6:4]=011 (±512°/s), CTRL3[3:0]=0100 (112.5 Hz ODR)
  qmiWriteReg(QMI_CTRL3, 0x34);

  // Low-pass filter enable for both accel and gyro
  qmiWriteReg(QMI_CTRL5, 0x11);

  // Enable accel + gyro
  qmiWriteReg(QMI_CTRL7, 0x03);

  delay(50);  // wait for first samples
  return true;
}

void qmiRead(int16_t out[6]) {
  // Read 6 bytes of accel (AX_L → AZ_H)
  Wire.beginTransmission(QMI_ADDR);
  Wire.write(QMI_AX_L);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)QMI_ADDR, (uint8_t)6);
  int16_t ax = Wire.read() | (Wire.read() << 8);  // little-endian
  int16_t ay = Wire.read() | (Wire.read() << 8);
  int16_t az = Wire.read() | (Wire.read() << 8);

  // Read 6 bytes of gyro (GX_L → GZ_H)
  Wire.beginTransmission(QMI_ADDR);
  Wire.write(QMI_GX_L);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)QMI_ADDR, (uint8_t)6);
  int16_t gx = Wire.read() | (Wire.read() << 8);  // little-endian
  int16_t gy = Wire.read() | (Wire.read() << 8);
  int16_t gz = Wire.read() | (Wire.read() << 8);

  out[0] = ax;
  out[1] = ay;
  out[2] = az;
  out[3] = gx;
  out[4] = gy;
  out[5] = gz;
}

// Pack 6 int16 values into buffer at offset (12 bytes, big-endian for wire)
void packIMU(int16_t vals[6], uint8_t* buf, int offset) {
  for (int i = 0; i < 6; i++) {
    buf[offset + i * 2]     = (vals[i] >> 8) & 0xFF;
    buf[offset + i * 2 + 1] = vals[i] & 0xFF;
  }
}

// --------------------------------------------------------------------
// Display rendering (240×280 ST7789V2)
// --------------------------------------------------------------------

void drawScoreScreen() {
  tft.fillScreen(TFT_BLACK);

  // State label at top
  const char* stateLabel;
  switch (displayState) {
    case STATE_CALIBRATING: stateLabel = "CALIBRATING..."; break;
    case STATE_WALKING:     stateLabel = "WALKING"; break;
    case STATE_DONE:        stateLabel = "SESSION DONE"; break;
    default:                stateLabel = "READY"; break;
  }
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextDatum(TC_DATUM);
  tft.setTextSize(2);
  tft.drawString(stateLabel, 120, 15);

  // Large score number
  uint16_t scoreColor = tftColors[displayColor];
  tft.setTextColor(scoreColor, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextSize(7);
  char scoreBuf[8];
  snprintf(scoreBuf, sizeof(scoreBuf), "%.0f", displayScore);
  tft.drawString(scoreBuf, 120, 115);

  // "GHS" label under score
  tft.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextSize(3);
  tft.drawString("GHS", 120, 175);

  // Color indicator text
  const char* colorLabel;
  switch (displayColor) {
    case COLOR_GREEN:  colorLabel = "GOOD"; break;
    case COLOR_YELLOW: colorLabel = "CAUTION"; break;
    case COLOR_RED:    colorLabel = "ATTENTION"; break;
    default:           colorLabel = "---"; break;
  }
  tft.setTextColor(scoreColor, TFT_BLACK);
  tft.setTextSize(2);
  tft.drawString(colorLabel, 120, 210);

  // Progress bar at bottom
  int barY = 250;
  int barH = 16;
  int barW = (int)(displayScore / 100.0 * 220);
  tft.fillRoundRect(10, barY, 220, barH, 4, TFT_DARKGREY);
  if (barW > 0) {
    tft.fillRoundRect(10, barY, barW, barH, 4, scoreColor);
  }
}

void drawCalibrationScreen() {
  tft.fillScreen(TFT_BLACK);

  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextSize(3);
  tft.drawString("STAND", 120, 100);
  tft.drawString("STILL", 120, 140);

  tft.setTextSize(1);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Calibrating sensors...", 120, 190);

  // Animated dots area
  tft.fillCircle(95, 220, 5, TFT_CYAN);
  tft.fillCircle(120, 220, 5, TFT_CYAN);
  tft.fillCircle(145, 220, 5, TFT_CYAN);
}

void drawIdleScreen() {
  tft.fillScreen(TFT_BLACK);

  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextSize(3);
  tft.drawString("GaitGuard", 120, 110);

  tft.setTextSize(1);
  tft.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
  tft.drawString("Waiting for Pi...", 120, 160);

  // WiFi status
  if (WiFi.status() == WL_CONNECTED) {
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.drawString(WiFi.localIP().toString().c_str(), 120, 200);
  } else {
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.drawString("WiFi disconnected", 120, 200);
  }
}

void updateDisplay() {
  if (!displayDirty) return;
  if (millis() - lastDisplayUpdate < 200) return;  // 5 Hz max refresh

  switch (displayState) {
    case STATE_IDLE:        drawIdleScreen(); break;
    case STATE_CALIBRATING: drawCalibrationScreen(); break;
    case STATE_WALKING:
    case STATE_DONE:        drawScoreScreen(); break;
  }

  displayDirty = false;
  lastDisplayUpdate = millis();
}

// --------------------------------------------------------------------
// WiFi connection
// --------------------------------------------------------------------

void connectWiFi() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextSize(2);
  tft.drawString("Connecting...", 120, 120);
  tft.setTextSize(1);
  tft.drawString(WIFI_SSID, 120, 160);

  Serial.printf("Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int dots = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    dots++;
    // Show progress on LCD
    tft.fillCircle(80 + (dots % 5) * 20, 200, 4, TFT_CYAN);
    if (dots % 5 == 0) {
      tft.fillRect(70, 190, 120, 20, TFT_BLACK);
    }
  }
  Serial.printf("\nConnected! IP: %s\n", WiFi.localIP().toString().c_str());

  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.setTextSize(2);
  tft.drawString("Connected!", 120, 110);
  tft.setTextSize(1);
  tft.drawString(WiFi.localIP().toString().c_str(), 120, 150);
  delay(1000);
}

// --------------------------------------------------------------------
// Setup & Loop
// --------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(100);

  // Backlight
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, HIGH);

  // LCD init
  tft.init();
  tft.setRotation(0);  // portrait 240×280
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE);
  tft.setTextDatum(MC_DATUM);
  tft.setTextSize(2);
  tft.drawString("GaitGuard", 120, 140);

  // I2C for IMU (QMI8658) on GPIO 11/10
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);

  if (!qmiInit()) {
    tft.fillScreen(TFT_RED);
    tft.setTextColor(TFT_WHITE, TFT_RED);
    tft.drawString("IMU ERROR", 120, 140);
    while (1) delay(1000);
  }
  Serial.println("QMI8658 initialized");

  // WiFi
  connectWiFi();

  // UDP sockets
  udpOut.begin(0);
  udpIn.begin(PORT_DISPLAY_CMD);
  Serial.printf("Listening for display cmds on port %d\n", PORT_DISPLAY_CMD);

  // Pre-fill header
  txBuf[0] = DEVICE_ID_FOOT;

  drawIdleScreen();
  lastSampleTime = millis();
}

void loop() {
  unsigned long now = millis();

  // --- 50 Hz IMU sampling & transmit ---
  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;

    int16_t footData[6];
    qmiRead(footData);

    txBuf[1] = (seqNum >> 8) & 0xFF;
    txBuf[2] = seqNum & 0xFF;
    packIMU(footData, txBuf, 3);

    udpOut.beginPacket(PI_IP, PORT_IMU_FOOT);
    udpOut.write(txBuf, 15);
    udpOut.endPacket();

    seqNum++;
  }

  // --- Check for display commands from Pi ---
  int packetSize = udpIn.parsePacket();
  if (packetSize >= 5) {
    uint8_t cmdBuf[6] = {0};
    udpIn.read(cmdBuf, min(packetSize, 6));

    uint8_t cmdType = cmdBuf[0];
    uint16_t rawScore = (cmdBuf[1] << 8) | cmdBuf[2];
    float newScore = rawScore / 10.0;
    uint8_t newColor = cmdBuf[3];
    uint8_t newState = cmdBuf[4];

    if (newColor > COLOR_RED) newColor = COLOR_RED;
    if (newState > STATE_DONE) newState = STATE_DONE;

    displayScore = newScore;
    displayColor = newColor;
    displayState = newState;
    displayDirty = true;

    Serial.printf("Display cmd: type=%d score=%.1f color=%d state=%d\n",
                  cmdType, newScore, newColor, newState);
  }

  // --- Refresh LCD ---
  updateDisplay();
}
