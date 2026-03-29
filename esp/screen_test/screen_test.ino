// Minimal screen test for Waveshare ESP32-S3-Touch-LCD-1.69
#include <TFT_eSPI.h>

TFT_eSPI tft = TFT_eSPI();

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("Screen test starting...");

  // Backlight on
  pinMode(15, OUTPUT);
  digitalWrite(15, HIGH);

  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_BLUE);

  tft.setTextColor(TFT_WHITE, TFT_BLUE);
  tft.setTextDatum(MC_DATUM);
  tft.setTextSize(3);
  tft.drawString("HELLO", 120, 140);

  Serial.println("Screen test done - should see blue screen with HELLO");
}

void loop() {
  delay(1000);
  Serial.println("alive");
}
