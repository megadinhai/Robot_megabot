#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

/*
 * Cấu hình phần cứng cho bo mạch ESP32-S3 tím (XH-S3E WiFi+BT N16R8)
 * Theo sơ đồ mạch esp32_s3_machtim.png:
 * Thiết bị: Chỉ có Loa (MAX98357A), Màn hình OLED SSD1306 (0.96 inch I2C) và Mic (INMP441)
 */

// ===================== ÂM THANH (AUDIO I2S SIMPLEX) =====================
#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 16000
#define AUDIO_I2S_METHOD_SIMPLEX

// Micro INMP441 (I2S Input)
#define AUDIO_I2S_MIC_GPIO_WS   GPIO_NUM_4   // Chân WS (LRCK)
#define AUDIO_I2S_MIC_GPIO_SCK  GPIO_NUM_5   // Chân SCK (BCLK)
#define AUDIO_I2S_MIC_GPIO_DIN  GPIO_NUM_6   // Chân SD (DIN vào ESP32)

// Mạch khuếch đại MAX98357A / Audio Amp (I2S Output)
#define AUDIO_I2S_SPK_GPIO_DOUT GPIO_NUM_7   // Chân DIN (DOUT từ ESP32)
#define AUDIO_I2S_SPK_GPIO_BCLK GPIO_NUM_15  // Chân BCLK
#define AUDIO_I2S_SPK_GPIO_LRCK GPIO_NUM_16  // Chân LRC (LRCK)
#define AUDIO_CODEC_PA_PIN      GPIO_NUM_17  // Chân PA Enable / SD_MODE kích hoạt công suất Loa

// ===================== MÀN HÌNH OLED 4 CHÂN (I2C) =====================
// Bo mạch XH-S3E WiFi+BT N16R8 (Màn hình 0.96 inch SSD1306 tích hợp)
#define DISPLAY_SDA_PIN GPIO_NUM_41
#define DISPLAY_SCL_PIN GPIO_NUM_42
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

// ===================== NÚT NHẤN BOOT =====================
#define BOOT_BUTTON_GPIO        GPIO_NUM_0

// ===================== ĐÈN LED CHỈ THỊ TRẠNG THÁI =====================
#define BUILTIN_LED_GPIO        GPIO_NUM_48

#endif // _BOARD_CONFIG_H_
