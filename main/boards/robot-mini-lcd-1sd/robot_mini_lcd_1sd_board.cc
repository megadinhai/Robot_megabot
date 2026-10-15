#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/oled_display.h"
#include "system_reset.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "pin_config.h"
#include "robot_controller.h"
#include "robot_admin_server.h"
#include "led/circular_strip.h"
#include "assets/lang_config.h"

#include <esp_log.h>
#include <esp_system.h>
#include <driver/gpio.h>
#include <driver/i2c_master.h>
#include <esp_lcd_panel_ops.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_timer.h>

#ifdef SH1106
#include <esp_lcd_panel_sh1106.h>
#endif

#define TAG "RobotMiniLcd1sdBoard"

class RobotAudioCodec : public NoAudioCodec {
private:
    int channel_mode_ = 0; // 0 = Left, 1 = Right, 2 = Both
    int log_counter_ = 0;
    float dc_x_prev_ = 0.0f;
    float dc_y_prev_ = 0.0f;
    int32_t max_val_accum_ = 0;

public:
    RobotAudioCodec(int input_sample_rate, int output_sample_rate,
                    gpio_num_t spk_bclk, gpio_num_t spk_ws, gpio_num_t spk_dout,
                    gpio_num_t mic_sck, gpio_num_t mic_ws, gpio_num_t mic_din) {
        duplex_ = false;
        input_sample_rate_ = input_sample_rate;
        output_sample_rate_ = output_sample_rate;

        // 1. Cấu hình TX (Loa MAX98357A)
        i2s_chan_config_t chan_cfg = {
            .id = XIAOZHI_I2S_PORT(0),
            .role = I2S_ROLE_MASTER,
            .dma_desc_num = AUDIO_CODEC_DMA_DESC_NUM,
            .dma_frame_num = AUDIO_CODEC_DMA_FRAME_NUM,
            .auto_clear_after_cb = true,
            .auto_clear_before_cb = false,
            .intr_priority = 0,
        };
        ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_handle_, nullptr));

        i2s_std_config_t spk_std_cfg = {
            .clk_cfg = {
                .sample_rate_hz = (uint32_t)output_sample_rate_,
                .clk_src = I2S_CLK_SRC_DEFAULT,
                .mclk_multiple = I2S_MCLK_MULTIPLE_256,
#ifdef I2S_HW_VERSION_2
                .ext_clk_freq_hz = 0,
#endif
            },
            .slot_cfg = {
                .data_bit_width = I2S_DATA_BIT_WIDTH_32BIT,
                .slot_bit_width = I2S_SLOT_BIT_WIDTH_AUTO,
                .slot_mode = I2S_SLOT_MODE_MONO,
                .slot_mask = I2S_STD_SLOT_LEFT,
                .ws_width = I2S_DATA_BIT_WIDTH_32BIT,
                .ws_pol = false,
                .bit_shift = true,
#ifdef I2S_HW_VERSION_2
                .left_align = true,
                .big_endian = false,
                .bit_order_lsb = false
#endif
            },
            .gpio_cfg = {
                .mclk = I2S_GPIO_UNUSED,
                .bclk = spk_bclk,
                .ws = spk_ws,
                .dout = spk_dout,
                .din = I2S_GPIO_UNUSED,
                .invert_flags = {
                    .mclk_inv = false,
                    .bclk_inv = false,
                    .ws_inv = false
                }
            }
        };
        ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_handle_, &spk_std_cfg));

        // 2. Cấu hình RX (Micro INMP441)
        chan_cfg.id = XIAOZHI_I2S_PORT(1);
        ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, nullptr, &rx_handle_));

        i2s_std_config_t mic_std_cfg = {
            .clk_cfg = {
                .sample_rate_hz = (uint32_t)input_sample_rate_,
                .clk_src = I2S_CLK_SRC_DEFAULT,
                .mclk_multiple = I2S_MCLK_MULTIPLE_256,
#ifdef I2S_HW_VERSION_2
                .ext_clk_freq_hz = 0,
#endif
            },
            .slot_cfg = {
                .data_bit_width = I2S_DATA_BIT_WIDTH_32BIT,
                .slot_bit_width = I2S_SLOT_BIT_WIDTH_AUTO,
                .slot_mode = I2S_SLOT_MODE_STEREO,
                .slot_mask = I2S_STD_SLOT_BOTH,
                .ws_width = I2S_DATA_BIT_WIDTH_32BIT,
                .ws_pol = false,
                .bit_shift = true,
#ifdef I2S_HW_VERSION_2
                .left_align = true,
                .big_endian = false,
                .bit_order_lsb = false
#endif
            },
            .gpio_cfg = {
                .mclk = I2S_GPIO_UNUSED,
                .bclk = mic_sck,
                .ws = mic_ws,
                .dout = I2S_GPIO_UNUSED,
                .din = mic_din,
                .invert_flags = {
                    .mclk_inv = false,
                    .bclk_inv = false,
                    .ws_inv = false
                }
            }
        };
        ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_handle_, &mic_std_cfg));

        ESP_LOGI(TAG, "Audio Codec initialized: Loa(BCLK=%d, LRC=%d, DOUT=%d), Mic(SCK=%d, WS=%d, DIN=%d)",
                 spk_bclk, spk_ws, spk_dout, mic_sck, mic_ws, mic_din);
    }

    virtual int Read(int16_t* dest, int samples) override {
        if (!rx_handle_) return 0;

        int32_t raw_stereo[samples * 2];
        size_t bytes_read = 0;
        esp_err_t ret = i2s_channel_read(rx_handle_, raw_stereo, samples * 2 * sizeof(int32_t), &bytes_read, pdMS_TO_TICKS(100));
        if (ret != ESP_OK || bytes_read == 0) {
            return 0;
        }

        int actual_samples = bytes_read / (2 * sizeof(int32_t));
        int64_t sum_left = 0;
        int64_t sum_right = 0;

        for (int i = 0; i < actual_samples; i++) {
            sum_left += std::abs(raw_stereo[i * 2]);
            sum_right += std::abs(raw_stereo[i * 2 + 1]);
        }

        if (channel_mode_ == 0 && sum_right > sum_left * 2 && sum_right > 500000) {
            channel_mode_ = 1;
            ESP_LOGI(TAG, "Mic: Switch sang kenh PHAI (Right channel)");
        } else if (channel_mode_ == 1 && sum_left > sum_right * 2 && sum_left > 500000) {
            channel_mode_ = 0;
            ESP_LOGI(TAG, "Mic: Switch sang kenh TRAI (Left channel)");
        }

        for (int i = 0; i < actual_samples; i++) {
            int32_t val = (channel_mode_ == 1) ? raw_stereo[i * 2 + 1] : raw_stereo[i * 2];
            int32_t s16 = val >> 14;

            float x = (float)s16;
            float y = x - dc_x_prev_ + 0.995f * dc_y_prev_;
            dc_x_prev_ = x;
            dc_y_prev_ = y;

            int32_t final_val = (int32_t)y;
            if (final_val > 32767) final_val = 32767;
            else if (final_val < -32768) final_val = -32768;

            dest[i] = (int16_t)final_val;
            if (std::abs(final_val) > max_val_accum_) {
                max_val_accum_ = std::abs(final_val);
            }
        }

        log_counter_++;
        if (log_counter_ >= 100) {
            log_counter_ = 0;
            ESP_LOGI(TAG, "MIC Diagnostic: AC Peak=%ld", (long)max_val_accum_);
            max_val_accum_ = 0;
        }

        return actual_samples;
    }
};

class RobotMiniLcd1sdBoard : public WifiBoard {
private:
    Button boot_button_;
    i2c_master_bus_handle_t i2c_bus_ = nullptr;
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    Display* display_ = nullptr;

    RobotPinConfig pin_cfg_;
    RobotCalibration calib_;
    RobotController* controller_ = nullptr;
    RobotAdminServer* admin_server_ = nullptr;

    void CheckBootSafeMode() {
        // Nếu người dùng bấm giữ nút BOOT trong 3 giây đầu khi vừa cấp nguồn -> Reset về mặc định
        gpio_set_direction((gpio_num_t)BOOT_BUTTON_GPIO, GPIO_MODE_INPUT);
        gpio_set_pull_mode((gpio_num_t)BOOT_BUTTON_GPIO, GPIO_PULLUP_ONLY);
        if (gpio_get_level((gpio_num_t)BOOT_BUTTON_GPIO) == 0) {
            ESP_LOGW(TAG, "Nut BOOT dang duoc giu khi bat nguon! Cho 3 giay de kiem tra che do Safe Reset...");
            int count = 0;
            for (int i = 0; i < 30; i++) {
                vTaskDelay(pdMS_TO_TICKS(100));
                if (gpio_get_level((gpio_num_t)BOOT_BUTTON_GPIO) == 0) {
                    count++;
                }
            }
            if (count >= 25) {
                ESP_LOGE(TAG, ">>> KICH HOAT SAFE RESET: XOA BAN DO CHAN, KHOI PHUC MAC DINH SO DO MACH! <<<");
                RobotPinConfig::ResetToDefaults();
                RobotCalibration::ResetToDefaults();
                vTaskDelay(pdMS_TO_TICKS(500));
                esp_restart();
            }
        }
    }

    void InitializeDisplayI2c() {
        i2c_master_bus_config_t bus_config = {
            .i2c_port = I2C_NUM_0,
            .sda_io_num = (gpio_num_t)pin_cfg_.oled_sda,
            .scl_io_num = (gpio_num_t)pin_cfg_.oled_scl,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = {
                .enable_internal_pullup = 1,
            },
        };
        ESP_ERROR_CHECK(i2c_new_master_bus(&bus_config, &i2c_bus_));
    }

    void InitializeOledDisplay() {
        esp_lcd_panel_io_i2c_config_t io_config = {
            .dev_addr = 0x3C,
            .scl_speed_hz = 400 * 1000,
            .control_phase_bytes = 1,
            .dc_bit_offset = 6,
            .lcd_cmd_bits = 8,
            .lcd_param_bits = 8,
            .on_color_trans_done = nullptr,
            .user_ctx = nullptr,
            .flags = {
                .dc_low_on_data = 0,
                .disable_control_phase = 0,
            },
        };
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c(i2c_bus_, &io_config, &panel_io_));

        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = GPIO_NUM_NC;
        panel_config.bits_per_pixel = 1;

        esp_lcd_panel_ssd1306_config_t ssd1306_config = {
            .height = static_cast<uint8_t>(pin_cfg_.oled_height),
        };
        panel_config.vendor_config = &ssd1306_config;

        esp_err_t err = ESP_OK;
        if (pin_cfg_.oled_chip == 1) {
#ifdef SH1106
            err = esp_lcd_new_panel_sh1106(panel_io_, &panel_config, &panel_);
#else
            err = esp_lcd_new_panel_ssd1306(panel_io_, &panel_config, &panel_);
#endif
        } else {
            err = esp_lcd_new_panel_ssd1306(panel_io_, &panel_config, &panel_);
        }

        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to install OLED driver: %s", esp_err_to_name(err));
            display_ = new NoDisplay();
            return;
        }

        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
        if (esp_lcd_panel_init(panel_) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to initialize OLED panel");
            display_ = new NoDisplay();
            return;
        }
        ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel_, false));
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));

        display_ = new OledDisplay(panel_io_, panel_, DISPLAY_WIDTH, pin_cfg_.oled_height, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
    }

    void InitializeButtons() {
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting) {
                EnterWifiConfigMode();
                return;
            }
            app.ToggleChatState();
        });

        boot_button_.OnLongPress([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() <= kDeviceStateStarting) {
                EnterWifiConfigMode();
            } else {
                app.ToggleChatState();
            }
        });
    }

    void InitializeAdminAndMotors() {
        // Khởi tạo điều khiển động cơ
        controller_ = new RobotController(
            (gpio_num_t)pin_cfg_.motor_in1,
            (gpio_num_t)pin_cfg_.motor_in2,
            (gpio_num_t)pin_cfg_.motor_in3,
            (gpio_num_t)pin_cfg_.motor_in4
        );
        controller_->SetCalibration(calib_.left_trim, calib_.right_trim, calib_.min_pwm, calib_.driver_type);

        // Khởi tạo máy chủ Web Quản trị Admin trên cổng 8080
        admin_server_ = new RobotAdminServer(pin_cfg_, calib_, controller_);
        admin_server_->Start(8080);
        ESP_LOGI(TAG, "DB-ROBOT Control Panel v2 running at http://0.0.0.0:8080");
    }

public:
    RobotMiniLcd1sdBoard() :
        boot_button_((gpio_num_t)BOOT_BUTTON_GPIO) {
        
        // 1. Kiểm tra an toàn nút BOOT
        CheckBootSafeMode();

        // 2. Nạp cấu hình chân NVS
        pin_cfg_.LoadFromNvs();
        calib_.LoadFromNvs();

        // 3. Khởi tạo OLED, Button, Motor và Web Admin
        InitializeDisplayI2c();
        InitializeOledDisplay();
        InitializeButtons();
        InitializeAdminAndMotors();
    }

    virtual Led* GetLed() override {
        if (pin_cfg_.led_rgb_din >= 0) {
            static CircularStrip led((gpio_num_t)pin_cfg_.led_rgb_din, pin_cfg_.led_rgb_count > 0 ? pin_cfg_.led_rgb_count : 1);
            return &led;
        }
        return nullptr;
    }

    virtual AudioCodec* GetAudioCodec() override {
        static RobotAudioCodec audio_codec(
            AUDIO_INPUT_SAMPLE_RATE,
            AUDIO_OUTPUT_SAMPLE_RATE,
            (gpio_num_t)pin_cfg_.spk_bclk,
            (gpio_num_t)pin_cfg_.spk_lrc,
            (gpio_num_t)pin_cfg_.spk_din,
            (gpio_num_t)pin_cfg_.mic_sck,
            (gpio_num_t)pin_cfg_.mic_ws,
            (gpio_num_t)pin_cfg_.mic_sd
        );
        return &audio_codec;
    }

    virtual void SetPowerSaveLevel(PowerSaveLevel level) override {
        WifiBoard::SetPowerSaveLevel(PowerSaveLevel::PERFORMANCE);
    }

    virtual Display* GetDisplay() override {
        return display_;
    }
};

DECLARE_BOARD(RobotMiniLcd1sdBoard);

