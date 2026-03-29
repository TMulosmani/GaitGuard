// TFT_eSPI User_Setup.h for Waveshare ESP32-S3-Touch-LCD-1.69
// Copy this file to your TFT_eSPI library folder, replacing the existing one.
// Location: Arduino/libraries/TFT_eSPI/User_Setup.h

#define ST7789_DRIVER

#define TFT_WIDTH  240
#define TFT_HEIGHT 280

// SPI pins
#define TFT_MOSI   7
#define TFT_SCLK   6
#define TFT_CS     5
#define TFT_DC     4
#define TFT_RST    8
#define TFT_BL     15

// SPI frequency
#define SPI_FREQUENCY       40000000
#define SPI_READ_FREQUENCY  20000000
#define SPI_TOUCH_FREQUENCY  2500000

// Color order
#define TFT_RGB_ORDER TFT_RGB

// Offsets for 240×280 on ST7789 (which is natively 240×320)
#define TFT_X_OFFSET 0
#define TFT_Y_OFFSET 20

#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_FONT8
#define LOAD_GFXFF
#define SMOOTH_FONT
