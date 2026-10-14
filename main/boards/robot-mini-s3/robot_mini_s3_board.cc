#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/oled_display.h"
#include "system_reset.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "led/circular_strip.h"
#include "assets/lang_config.h"

#include <esp_log.h>
#include <esp_system.h>
#include <driver/gpio.h>
#include <driver/i2c_master.h>
#include <esp_lcd_panel_ops.h>
#include <esp_lcd_panel_vendor.h>

#ifdef SH1106
#include <esp_lcd_panel_sh1106.h>
#endif

#define TAG "RobotMiniS3Board"

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

        // 2. Cấu hình RX (Micro I2S) ở chế độ STEREO (I2S_STD_SLOT_BOTH)
        // Việc cấu hình STEREO đảm bảo dù chân L/R của Mic INMP441 nối GND hay nối VDD/treo,
        // ESP32 đều thu được cả 2 kênh và thuật toán Read() sẽ tự động lấy dữ liệu từ kênh có tiếng!
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
        ESP_LOGI(TAG, "RobotAudioCodec initialized: Speaker mono, Mic stereo capture on WS=%d, SCK=%d, DIN=%d",
                 mic_ws, mic_sck, mic_din);
    }

    virtual int Read(int16_t* dest, int samples) override {
        // samples là số lượng mẫu mono cần trả về cho audio pipeline (input_channels = 1)
        // Vì RX được mở ở chế độ STEREO (2 kênh Left + Right, mỗi mẫu 32-bit), cần đọc 2 * samples số mẫu 32-bit.
        size_t bytes_read = 0;
        constexpr uint32_t kReadTimeoutMs = 100;
        std::vector<int32_t> stereo_buf(samples * 2);

        esp_err_t err = i2s_channel_read(rx_handle_, stereo_buf.data(), samples * 2 * sizeof(int32_t), &bytes_read, kReadTimeoutMs);
        if (err != ESP_OK || bytes_read == 0) {
            return 0;
        }

        int stereo_samples_read = bytes_read / sizeof(int32_t);
        int mono_samples = stereo_samples_read / 2;

        int32_t max_val = 0;

        for (int i = 0; i < mono_samples; i++) {
            // INMP441 gửi dữ liệu 24-bit MSB-aligned trên kênh Trái (L/R nối GND).
            // Dịch >> 12 cho mức âm lượng chuẩn rõ ràng (+24dB trên dải 16-bit).
            float raw_val = (float)(stereo_buf[i * 2] >> 12);

            // Bộ lọc High-Pass DC-Blocker (IIR single-pole, fc ~ 13Hz tại 16kHz):
            // y[n] = x[n] - x[n-1] + 0.995 * y[n-1]
            // Loại bỏ 100% độ lệch một chiều (DC offset) vốn làm nghẽn VAD & MultiNet!
            float filtered = raw_val - dc_x_prev_ + 0.995f * dc_y_prev_;
            dc_x_prev_ = raw_val;
            dc_y_prev_ = filtered;

            int32_t chosen = (int32_t)filtered;
            if (chosen > INT16_MAX) chosen = INT16_MAX;
            if (chosen < -INT16_MAX) chosen = -INT16_MAX;
            if (std::abs(chosen) > max_val_accum_) max_val_accum_ = std::abs(chosen);

            dest[i] = (int16_t)chosen;
        }

        // In chẩn đoán biên độ AC định kỳ mỗi 200ms (5 lần / giây) để theo dõi siêu nhạy
        if (++log_counter_ >= 20) {
            log_counter_ = 0;
            ESP_LOGI(TAG, "MIC Diagnostic: AC Peak=%ld", (long)max_val_accum_);
            max_val_accum_ = 0;
        }

        return mono_samples;
    }
};

class RobotMiniS3Board : public WifiBoard {
private:
    i2c_master_bus_handle_t display_i2c_bus_ = nullptr;
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    Display* display_ = nullptr;
    Button boot_button_;

    void InitializePowerAmp() {
#if defined(AUDIO_CODEC_PA_PIN) && (AUDIO_CODEC_PA_PIN != GPIO_NUM_NC)
        ESP_LOGI(TAG, "Enabling Audio Amplifier (PA_EN) on GPIO %d", AUDIO_CODEC_PA_PIN);
        gpio_reset_pin((gpio_num_t)AUDIO_CODEC_PA_PIN);
        gpio_set_direction((gpio_num_t)AUDIO_CODEC_PA_PIN, GPIO_MODE_OUTPUT);
        gpio_set_level((gpio_num_t)AUDIO_CODEC_PA_PIN, 1);
#endif
    }

    void InitializeDisplayI2c() {
        i2c_master_bus_config_t bus_config = {
            .i2c_port = (i2c_port_t)0,
            .sda_io_num = DISPLAY_SDA_PIN,
            .scl_io_num = DISPLAY_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = {
                .enable_internal_pullup = 1,
            },
        };
        esp_err_t err = i2c_new_master_bus(&bus_config, &display_i2c_bus_);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to create I2C bus: %s", esp_err_to_name(err));
            display_ = new NoDisplay();
        }
    }

    void InitializeOledDisplay() {
        if (display_ != nullptr || display_i2c_bus_ == nullptr) return;

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

        esp_err_t err = esp_lcd_new_panel_io_i2c(display_i2c_bus_, &io_config, &panel_io_);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to create OLED panel IO: %s", esp_err_to_name(err));
            display_ = new NoDisplay();
            return;
        }

        ESP_LOGI(TAG, "Installing OLED SSD1306 driver (Width=%d, Height=%d)", DISPLAY_WIDTH, DISPLAY_HEIGHT);
        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = GPIO_NUM_NC;
        panel_config.bits_per_pixel = 1;

        esp_lcd_panel_ssd1306_config_t ssd1306_config = {
            .height = static_cast<uint8_t>(DISPLAY_HEIGHT),
        };
        panel_config.vendor_config = &ssd1306_config;

#ifdef SH1106
        err = esp_lcd_new_panel_sh1106(panel_io_, &panel_config, &panel_);
#else
        err = esp_lcd_new_panel_ssd1306(panel_io_, &panel_config, &panel_);
#endif

        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to install OLED driver: %s", esp_err_to_name(err));
            display_ = new NoDisplay();
            return;
        }

        // Reset & Initialize panel
        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
        if (esp_lcd_panel_init(panel_) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to initialize OLED panel");
            display_ = new NoDisplay();
            return;
        }
        ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel_, false));
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));

        display_ = new OledDisplay(panel_io_, panel_, DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
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

public:
    RobotMiniS3Board() :
        boot_button_((gpio_num_t)BOOT_BUTTON_GPIO) {
        InitializePowerAmp();
        InitializeDisplayI2c();
        InitializeOledDisplay();
        InitializeButtons();
    }

    virtual Led* GetLed() override {
        // Đèn LED RGB WS2812 tích hợp (GPIO 48)
        if (BUILTIN_LED_GPIO != GPIO_NUM_NC) {
            static CircularStrip led((gpio_num_t)BUILTIN_LED_GPIO, 1);
            return &led;
        }
        return nullptr;
    }

    virtual AudioCodec* GetAudioCodec() override {
        static RobotAudioCodec audio_codec(
            AUDIO_INPUT_SAMPLE_RATE,
            AUDIO_OUTPUT_SAMPLE_RATE,
            (gpio_num_t)AUDIO_I2S_SPK_GPIO_BCLK,
            (gpio_num_t)AUDIO_I2S_SPK_GPIO_LRCK,
            (gpio_num_t)AUDIO_I2S_SPK_GPIO_DOUT,
            (gpio_num_t)AUDIO_I2S_MIC_GPIO_SCK,
            (gpio_num_t)AUDIO_I2S_MIC_GPIO_WS,
            (gpio_num_t)AUDIO_I2S_MIC_GPIO_DIN
        );
        return &audio_codec;
    }

    virtual void SetPowerSaveLevel(PowerSaveLevel level) override {
        // Luon giu WiFi o che do PERFORMANCE de duy tri ket noi WebSocket on dinh voi Render
        WifiBoard::SetPowerSaveLevel(PowerSaveLevel::PERFORMANCE);
    }

    virtual Display* GetDisplay() override {
        return display_;
    }
};

DECLARE_BOARD(RobotMiniS3Board);
