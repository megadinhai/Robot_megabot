#ifndef _PIN_CONFIG_H_
#define _PIN_CONFIG_H_

#include <cstdint>
#include <string>
#include <driver/gpio.h>
#include "config.h"
#include "settings.h"

struct RobotPinConfig {
    // Động cơ bánh xe (MX1616 / DRV8833 / L298N Mini)
    int8_t motor_in1 = MOTOR_LEFT_IN1_GPIO;   // GPIO 1  (Bánh trái tiến)
    int8_t motor_in2 = MOTOR_LEFT_IN2_GPIO;   // GPIO 2  (Bánh trái lùi)
    int8_t motor_in3 = MOTOR_RIGHT_IN3_GPIO;  // GPIO 9  (Bánh phải tiến)
    int8_t motor_in4 = MOTOR_RIGHT_IN4_GPIO;  // GPIO 10 (Bánh phải lùi)

    // Màn hình OLED I2C (Tích hợp trên bo mạch XH-S3E)
    int8_t oled_sda = DISPLAY_SDA_PIN;        // GPIO 41
    int8_t oled_scl = DISPLAY_SCL_PIN;        // GPIO 42
    int8_t oled_chip = 0;                     // 0: SSD1306, 1: SH1106
    int8_t oled_height = DISPLAY_HEIGHT;      // 64 hoặc 32

    // Micro INMP441
    int8_t mic_ws = AUDIO_I2S_MIC_GPIO_WS;    // GPIO 4
    int8_t mic_sck = AUDIO_I2S_MIC_GPIO_SCK;  // GPIO 5
    int8_t mic_sd = AUDIO_I2S_MIC_GPIO_DIN;   // GPIO 6

    // Loa MAX98357A
    int8_t spk_din = AUDIO_I2S_SPK_GPIO_DOUT; // GPIO 7
    int8_t spk_bclk = AUDIO_I2S_SPK_GPIO_BCLK;// GPIO 15
    int8_t spk_lrc = AUDIO_I2S_SPK_GPIO_LRCK; // GPIO 16

    // Đèn LED
    int8_t led_rgb_din = BUILTIN_LED_GPIO;    // GPIO 48
    int16_t led_rgb_count = WS2812_LED_COUNT; // 8 bóng
    int8_t lamp_gpio = LAMP_GPIO;             // GPIO 21 (Dây tóc LED / Đèn hiệu)

    // Cảm biến chạm TTP223
    int8_t touch_gpio = TOUCH_BUTTON_GPIO;    // GPIO 0
    int8_t touch_level = 0;                   // 0: Thấp (Active Low), 1: Cao (Active High)

    // Cảm biến an toàn
    int8_t vl53_sda = VL53L0X_SDA_GPIO;       // GPIO 10
    int8_t vl53_scl = VL53L0X_SCL_GPIO;       // GPIO 11
    int8_t vl53_xshut = -1;                   // -1: Không dùng
    int8_t hcsr04_trig = ULTRASONIC_TRIG_GPIO;// GPIO 13
    int8_t hcsr04_echo = ULTRASONIC_ECHO_GPIO;// GPIO 12

    // Thẻ nhớ SD (SPI)
    int8_t sd_miso = SD_MISO_GPIO;            // GPIO 40
    int8_t sd_mosi = SD_MOSI_GPIO;            // GPIO 38
    int8_t sd_clk = SD_CLK_GPIO;              // GPIO 39
    int8_t sd_cs = SD_CS_GPIO;                // GPIO 47

    // Pin & Đo điện áp
    int8_t bat_adc = POTENTIOMETER_ADC_GPIO;  // GPIO 14
    int8_t bat_chrg = -1;                     // -1: Không dùng

    // Nạp từ NVS
    void LoadFromNvs() {
        Settings nvs("robot_pins", false);
        int cfg_ver = nvs.GetInt("cfg_ver", 0);
        if (cfg_ver < 2) {
            // Phiên bản NVS cũ hoặc chưa cấu hình -> dùng mặc định mới cho bo mạch XH-S3E
            return;
        }

        motor_in1 = nvs.GetInt("m_in1", motor_in1);
        motor_in2 = nvs.GetInt("m_in2", motor_in2);
        motor_in3 = nvs.GetInt("m_in3", motor_in3);
        motor_in4 = nvs.GetInt("m_in4", motor_in4);

        oled_sda = nvs.GetInt("o_sda", oled_sda);
        oled_scl = nvs.GetInt("o_scl", oled_scl);
        oled_chip = nvs.GetInt("o_chip", oled_chip);
        oled_height = nvs.GetInt("o_h", oled_height);

        mic_ws = nvs.GetInt("mic_ws", mic_ws);
        mic_sck = nvs.GetInt("mic_sck", mic_sck);
        mic_sd = nvs.GetInt("mic_sd", mic_sd);

        spk_din = nvs.GetInt("spk_din", spk_din);
        spk_bclk = nvs.GetInt("spk_bclk", spk_bclk);
        spk_lrc = nvs.GetInt("spk_lrc", spk_lrc);

        led_rgb_din = nvs.GetInt("rgb_din", led_rgb_din);
        led_rgb_count = nvs.GetInt("rgb_cnt", led_rgb_count);
        lamp_gpio = nvs.GetInt("lamp_io", lamp_gpio);

        touch_gpio = nvs.GetInt("tch_io", touch_gpio);
        touch_level = nvs.GetInt("tch_lvl", touch_level);

        vl53_sda = nvs.GetInt("vl_sda", vl53_sda);
        vl53_scl = nvs.GetInt("vl_scl", vl53_scl);
        vl53_xshut = nvs.GetInt("vl_xsh", vl53_xshut);
        hcsr04_trig = nvs.GetInt("hc_trig", hcsr04_trig);
        hcsr04_echo = nvs.GetInt("hc_echo", hcsr04_echo);

        sd_miso = nvs.GetInt("sd_miso", sd_miso);
        sd_mosi = nvs.GetInt("sd_mosi", sd_mosi);
        sd_clk = nvs.GetInt("sd_clk", sd_clk);
        sd_cs = nvs.GetInt("sd_cs", sd_cs);

        bat_adc = nvs.GetInt("bat_adc", bat_adc);
        bat_chrg = nvs.GetInt("bat_chrg", bat_chrg);
    }

    // Lưu vào NVS
    void SaveToNvs() const {
        Settings nvs("robot_pins", true);
        nvs.SetInt("cfg_ver", 2);
        nvs.SetInt("m_in1", motor_in1);
        nvs.SetInt("m_in2", motor_in2);
        nvs.SetInt("m_in3", motor_in3);
        nvs.SetInt("m_in4", motor_in4);

        nvs.SetInt("o_sda", oled_sda);
        nvs.SetInt("o_scl", oled_scl);
        nvs.SetInt("o_chip", oled_chip);
        nvs.SetInt("o_h", oled_height);

        nvs.SetInt("mic_ws", mic_ws);
        nvs.SetInt("mic_sck", mic_sck);
        nvs.SetInt("mic_sd", mic_sd);

        nvs.SetInt("spk_din", spk_din);
        nvs.SetInt("spk_bclk", spk_bclk);
        nvs.SetInt("spk_lrc", spk_lrc);

        nvs.SetInt("rgb_din", led_rgb_din);
        nvs.SetInt("rgb_cnt", led_rgb_count);
        nvs.SetInt("lamp_io", lamp_gpio);

        nvs.SetInt("tch_io", touch_gpio);
        nvs.SetInt("tch_lvl", touch_level);

        nvs.SetInt("vl_sda", vl53_sda);
        nvs.SetInt("vl_scl", vl53_scl);
        nvs.SetInt("vl_xsh", vl53_xshut);
        nvs.SetInt("hc_trig", hcsr04_trig);
        nvs.SetInt("hc_echo", hcsr04_echo);

        nvs.SetInt("sd_miso", sd_miso);
        nvs.SetInt("sd_mosi", sd_mosi);
        nvs.SetInt("sd_clk", sd_clk);
        nvs.SetInt("sd_cs", sd_cs);

        nvs.SetInt("bat_adc", bat_adc);
        nvs.SetInt("bat_chrg", bat_chrg);
    }

    // Xoá cấu hình NVS trở về mặc định
    static void ResetToDefaults() {
        Settings nvs("robot_pins", true);
        nvs.EraseAll();
    }
};

struct RobotCalibration {
    int8_t left_trim = 0;         // -50 .. +50 %
    int8_t right_trim = 0;        // -50 .. +50 %
    uint8_t min_pwm = 20;         // 0 .. 255 (Ngưỡng chết PWM)
    uint8_t driver_type = 0;      // 0: MX1616 / DRV8833, 1: L298N Mini

    // Cảm biến an toàn
    uint8_t safety_mode = 0;      // 0: Chống rơi mép bàn, 1: Tránh vật cản
    uint16_t obstacle_cm = 28;    // Ngưỡng vật cản cm
    uint16_t cliff_mm = 50;       // Ngưỡng mép bàn mm
    bool laser_enabled = true;

    // Pin
    uint16_t bat_min_raw = 2100;
    uint16_t bat_max_raw = 2770;

    void LoadFromNvs() {
        Settings nvs("robot_calib", false);
        left_trim = nvs.GetInt("l_trim", left_trim);
        right_trim = nvs.GetInt("r_trim", right_trim);
        min_pwm = nvs.GetInt("min_pwm", min_pwm);
        driver_type = nvs.GetInt("drv_t", driver_type);

        safety_mode = nvs.GetInt("safe_m", safety_mode);
        obstacle_cm = nvs.GetInt("obs_cm", obstacle_cm);
        cliff_mm = nvs.GetInt("clf_mm", cliff_mm);
        laser_enabled = nvs.GetBool("las_en", laser_enabled);

        bat_min_raw = nvs.GetInt("bat_min", bat_min_raw);
        bat_max_raw = nvs.GetInt("bat_max", bat_max_raw);
    }

    void SaveToNvs() const {
        Settings nvs("robot_calib", true);
        nvs.SetInt("l_trim", left_trim);
        nvs.SetInt("r_trim", right_trim);
        nvs.SetInt("min_pwm", min_pwm);
        nvs.SetInt("drv_t", driver_type);

        nvs.SetInt("safe_m", safety_mode);
        nvs.SetInt("obs_cm", obstacle_cm);
        nvs.SetInt("clf_mm", cliff_mm);
        nvs.SetBool("las_en", laser_enabled);

        nvs.SetInt("bat_min", bat_min_raw);
        nvs.SetInt("bat_max", bat_max_raw);
    }

    static void ResetToDefaults() {
        Settings nvs("robot_calib", true);
        nvs.EraseAll();
    }
};

#endif // _PIN_CONFIG_H_

