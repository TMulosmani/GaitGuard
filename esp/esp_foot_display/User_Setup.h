// TFT_eSPI User_Setup.h for Waveshare ESP32-S3-Touch-LCD-1.69
// ST7789V2, 240×280, ESP32-S3

#define USER_SETUP_LOADED 1

#define ST7789_DRIVER
#define INIT_SEQUENCE_3  // ST7789V2 init sequence

#define TFT_WIDTH  240
#define TFT_HEIGHT 280

// Waveshare ESP32-S3-LCD-1.69 SPI pins
#define TFT_MOSI   7
#define TFT_SCLK   6
#define TFT_CS     5
#define TFT_DC     4
#define TFT_RST    8
#define TFT_BL     15

// No MISO needed for write-only display
#define TFT_MISO   -1

// Use the HSPI port on ESP32-S3
#define USE_HSPI_PORT

// SPI frequency
#define SPI_FREQUENCY       40000000
#define SPI_READ_FREQUENCY  16000000

// Color order — ST7789V2 uses RGB
#define TFT_RGB_ORDER TFT_RGB

// Inversion — ST7789 typically needs inversion on
#define TFT_INVERSION_ON

// Load fonts
#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_FONT8
#define LOAD_GFXFF
#define SMOOTH_FONT
