/*
 * WiFi Test — Access Point (upload to ESP32-S3, foot board)
 *
 * Creates the "GaitGuard" WiFi network and prints when clients connect.
 * Open Serial Monitor at 115200 to see status.
 */

#include <WiFi.h>
#include <esp_wifi.h>
#include "../config.h"

void setup() {
  Serial.begin(115200);
  // Wait for USB CDC serial on ESP32-S3 (up to 5 seconds)
  unsigned long t = millis();
  while (!Serial && (millis() - t < 5000)) { delay(10); }
  delay(500);
  Serial.println("\n=== WiFi Test: ACCESS POINT ===");

  // Set up soft AP
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD, /*channel=*/1, /*hidden=*/0, /*max_conn=*/4);

  // Give AP time to start
  delay(500);

  Serial.print("AP SSID:      ");
  Serial.println(AP_SSID);
  Serial.print("AP IP:        ");
  Serial.println(WiFi.softAPIP());
  Serial.println("Waiting for clients to connect...\n");
}

void loop() {
  static int lastCount = -1;
  int count = WiFi.softAPgetStationNum();

  if (count != lastCount) {
    Serial.print("[AP] Connected clients: ");
    Serial.println(count);
    lastCount = count;

    if (count > 0) {
      Serial.println("[AP] *** Client connected! WiFi link is up. ***");
    }
  }

  delay(1000);
}
