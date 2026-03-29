// Bare minimum WiFi test for ESP32-S3
#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("WiFi test starting...");
  WiFi.mode(WIFI_STA);
  WiFi.begin("Arsh iPhone", "12345678");

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(1000);
    Serial.printf("status=%d\n", WiFi.status());
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("CONNECTED! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.printf("FAILED. Final status=%d\n", WiFi.status());
  }
}

void loop() {}
