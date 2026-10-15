#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

/*
 * Cấu hình phần cứng cho bo mạch Robot_Mini_LCD_1SD (ESP32-S3 WROOM-1 N16R8)
 * Sơ đồ chân theo tài liệu SoDoMach/Robot_Mini_LCD_1SD/Robot_Mini_LCD_1SD.jpg
 */

// ===================== ÂM THANH (AUDIO I2S SIMPLEX) =====================
#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 16000
#define AUDIO_I2S_METHOD_SIMPLEX

// Micro INMP441 (I2S Input)
#define AUDIO_I2S_MIC_GPIO_DIN  GPIO_NUM_4   // Chân SD (DOUT của Mic vào ESP32)
#define AUDIO_I2S_MIC_GPIO_WS   GPIO_NUM_15  // Chân WS (LRCK)
#define AUDIO_I2S_MIC_GPIO_SCK  GPIO_NUM_16  // Chân SCK (BCLK)

// Loa MAX98357A (I2S Output)
#define AUDIO_I2S_SPK_GPIO_DOUT GPIO_NUM_7   // Chân DIN (DOUT từ ESP32 sang Loa)
#define AUDIO_I2S_SPK_GPIO_BCLK GPIO_NUM_5   // Chân BCLK
#define AUDIO_I2S_SPK_GPIO_LRCK GPIO_NUM_6   // Chân LRC (LRCK)
#define AUDIO_CODEC_PA_PIN      GPIO_NUM_NC  // Nối nguồn trực tiếp

// ===================== MÀN HÌNH OLED 4 CHÂN (I2C) =====================
// OLED SSD1306 / SH1106 I2C (0.96 inch 128x64)
#define DISPLAY_SDA_PIN GPIO_NUM_3
#define DISPLAY_SCL_PIN GPIO_NUM_8
#define DISPLAY_WIDTH   128

#if CONFIG_OLED_SSD1306_128X32
#define DISPLAY_HEIGHT  32
#elif CONFIG_OLED_SSD1306_128X64
#define DISPLAY_HEIGHT  64
#elif CONFIG_OLED_SH1106_128X64
#define DISPLAY_HEIGHT  64
#define SH1106
#else
#define DISPLAY_HEIGHT  64
#endif

#define DISPLAY_MIRROR_X true
#define DISPLAY_MIRROR_Y true

// ===================== ĐỘNG CƠ BÁNH XE (MX1616 / DRV8833) =====================
#define MOTOR_LEFT_IN1_GPIO     GPIO_NUM_1   // Bánh trái tiến
#define MOTOR_LEFT_IN2_GPIO     GPIO_NUM_2   // Bánh trái lùi
#define MOTOR_RIGHT_IN3_GPIO    GPIO_NUM_42  // Bánh phải tiến
#define MOTOR_RIGHT_IN4_GPIO    GPIO_NUM_41  // Bánh phải lùi

// ===================== THẺ NHỚ SD MINI (SPI) =====================
#define SD_MISO_GPIO            GPIO_NUM_40
#define SD_CLK_GPIO             GPIO_NUM_45
#define SD_MOSI_GPIO            GPIO_NUM_48
#define SD_CS_GPIO              GPIO_NUM_47

// ===================== CẢM BIẾN AN TOÀN =====================
#define VL53L0X_SDA_GPIO        GPIO_NUM_46
#define VL53L0X_SCL_GPIO        GPIO_NUM_9
#define ULTRASONIC_TRIG_GPIO    GPIO_NUM_13
#define ULTRASONIC_ECHO_GPIO    GPIO_NUM_14

// ===================== CẢM BIẾN CHẠM TTP223 =====================
#define TOUCH_BUTTON_GPIO       GPIO_NUM_21

// ===================== ĐÈN LED RGB WS2812 =====================
#define BUILTIN_LED_GPIO        GPIO_NUM_20
#define WS2812_LED_COUNT        8
#define LAMP_GPIO               GPIO_NUM_21

// ===================== PIN & ĐO ĐIỆN ÁP =====================
#define POTENTIOMETER_ADC_GPIO  GPIO_NUM_12

// ===================== NÚT NHẤN BOOT =====================
#define BOOT_BUTTON_GPIO        GPIO_NUM_0

#endif // _BOARD_CONFIG_H_

