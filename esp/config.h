// GaitGuard — Shared WiFi + network config for both ESPs
// Edit these values for your network

#ifndef GAITGUARD_CONFIG_H
#define GAITGUARD_CONFIG_H

// WiFi credentials
#define WIFI_SSID "UNH_ROBOT_5"
#define WIFI_PASSWORD "unh@robot11"

// Raspberry Pi IP address (qnxpi)
#define PI_IP "192.168.1.249"

// UDP ports — must match pi/wifi_receiver.py
#define PORT_IMU_THIGH_SHIN 5001 // ESP#1 → Pi (IMU data)
#define PORT_IMU_FOOT 5002       // ESP#2 → Pi (IMU data)
#define PORT_HAPTIC_CMD 5003     // Pi → ESP#1 (haptic commands)
#define PORT_DISPLAY_CMD 5004    // Pi → ESP#2 (display updates)

// Sensor rate
#define SAMPLE_INTERVAL_MS 20 // 50 Hz

// Device IDs (first byte of every packet)
#define DEVICE_ID_THIGH_SHIN 0x01
#define DEVICE_ID_FOOT 0x02

#endif
