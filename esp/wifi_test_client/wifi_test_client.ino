/*
 * WiFi Test — Client (upload to ESP32, thigh/shin board)
 *
 * Connects to the "GaitGuard" AP hosted by the other ESP.
 * Open Serial Monitor at 115200 to see status.
 */

#include <WiFi.h>
#include <esp_wifi.h>
#include "../config.h"

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== WiFi Test: CLIENT ===");

  WiFi.mode(WIFI_STA);
  WiFi.begin(AP_SSID, AP_PASSWORD);

  Serial.print("Connecting to \"");
  Serial.print(AP_SSID);
  Serial.print("\"");

  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }

  Serial.println(" connected!");
  Serial.print("My IP:        ");
  Serial.println(WiFi.localIP());
  Serial.print("Gateway (AP): ");
  Serial.println(WiFi.gatewayIP());
  Serial.print("RSSI:         ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  Serial.println("\n[CLIENT] *** WiFi link is up! ***");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[CLIENT] Disconnected! Reconnecting...");
    WiFi.begin(AP_SSID, AP_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
      Serial.print(".");
      delay(500);
    }
    Serial.println(" reconnected!");
    Serial.print("My IP: ");
    Serial.println(WiFi.localIP());
  }

  Serial.print("[CLIENT] Still connected | RSSI: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  delay(3000);
}
