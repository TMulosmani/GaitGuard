#include <Wire.h>

#define MPU1 0x68  // AD0 → GND
#define MPU2 0x69  // AD0 → 3.3V

void wakeup(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);
}

void readMPU(uint8_t addr, int16_t &ax, int16_t &ay, int16_t &az,
                            int16_t &gx, int16_t &gy, int16_t &gz) {
  Wire.beginTransmission(addr);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(addr, 14, true);

  ax = Wire.read() << 8 | Wire.read();
  ay = Wire.read() << 8 | Wire.read();
  az = Wire.read() << 8 | Wire.read();
  Wire.read(); Wire.read(); // skip temp
  gx = Wire.read() << 8 | Wire.read();
  gy = Wire.read() << 8 | Wire.read();
  gz = Wire.read() << 8 | Wire.read();
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  wakeup(MPU1);
  wakeup(MPU2);
}

void loop() {
  int16_t ax1, ay1, az1, gx1, gy1, gz1;
  int16_t ax2, ay2, az2, gx2, gy2, gz2;

  readMPU(MPU1, ax1, ay1, az1, gx1, gy1, gz1);
  readMPU(MPU2, ax2, ay2, az2, gx2, gy2, gz2);

  Serial.printf("MPU1  Accel X:%6d Y:%6d Z:%6d  Gyro X:%6d Y:%6d Z:%6d\n", ax1, ay1, az1, gx1, gy1, gz1);
  Serial.printf("MPU2  Accel X:%6d Y:%6d Z:%6d  Gyro X:%6d Y:%6d Z:%6d\n\n", ax2, ay2, az2, gx2, gy2, gz2);

  delay(100);
}
