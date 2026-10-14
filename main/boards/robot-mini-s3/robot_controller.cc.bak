#include "robot_controller.h"
#include "mcp_server.h"
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <algorithm>

#define TAG "RobotController"

#define LEDC_SPEED_MODE      LEDC_LOW_SPEED_MODE
#define LEDC_DUTY_RES        LEDC_TIMER_8_BIT
#define LEDC_FREQUENCY       (1000) // 1 kHz PWM

#define CH_LEFT_IN1          LEDC_CHANNEL_0
#define CH_LEFT_IN2          LEDC_CHANNEL_1
#define CH_RIGHT_IN3         LEDC_CHANNEL_2
#define CH_RIGHT_IN4         LEDC_CHANNEL_3

RobotController::RobotController(gpio_num_t left_in1, gpio_num_t left_in2,
                                 gpio_num_t right_in3, gpio_num_t right_in4)
    : left_in1_(left_in1), left_in2_(left_in2),
      right_in3_(right_in3), right_in4_(right_in4) {

    ESP_LOGI(TAG, "Initializing Robot MX1616 Motor Controller: L=[%d, %d], R=[%d, %d]",
             left_in1_, left_in2_, right_in3_, right_in4_);

    if (left_in1_ == GPIO_NUM_NC || left_in2_ == GPIO_NUM_NC ||
        right_in3_ == GPIO_NUM_NC || right_in4_ == GPIO_NUM_NC) {
        ESP_LOGW(TAG, "Motor pins not fully assigned, controller disabled");
        return;
    }

    // Configure LEDC Timer
    ledc_timer_config_t timer_cfg = {
        .speed_mode = LEDC_SPEED_MODE,
        .duty_resolution = LEDC_DUTY_RES,
        .timer_num = LEDC_TIMER_1,
        .freq_hz = LEDC_FREQUENCY,
        .clk_cfg = LEDC_AUTO_CLK,
        .deconfigure = false
    };
    ESP_ERROR_CHECK(ledc_timer_config(&timer_cfg));

    // Configure 4 PWM channels
    ledc_channel_config_t ch_cfg[4] = {
        {
            .gpio_num = left_in1_,
            .speed_mode = LEDC_SPEED_MODE,
            .channel = CH_LEFT_IN1,
            .intr_type = LEDC_INTR_DISABLE,
            .timer_sel = LEDC_TIMER_1,
            .duty = 0,
            .hpoint = 0,
            .flags = { .output_invert = 0 }
        },
        {
            .gpio_num = left_in2_,
            .speed_mode = LEDC_SPEED_MODE,
            .channel = CH_LEFT_IN2,
            .intr_type = LEDC_INTR_DISABLE,
            .timer_sel = LEDC_TIMER_1,
            .duty = 0,
            .hpoint = 0,
            .flags = { .output_invert = 0 }
        },
        {
            .gpio_num = right_in3_,
            .speed_mode = LEDC_SPEED_MODE,
            .channel = CH_RIGHT_IN3,
            .intr_type = LEDC_INTR_DISABLE,
            .timer_sel = LEDC_TIMER_1,
            .duty = 0,
            .hpoint = 0,
            .flags = { .output_invert = 0 }
        },
        {
            .gpio_num = right_in4_,
            .speed_mode = LEDC_SPEED_MODE,
            .channel = CH_RIGHT_IN4,
            .intr_type = LEDC_INTR_DISABLE,
            .timer_sel = LEDC_TIMER_1,
            .duty = 0,
            .hpoint = 0,
            .flags = { .output_invert = 0 }
        }
    };

    for (int i = 0; i < 4; i++) {
        ESP_ERROR_CHECK(ledc_channel_config(&ch_cfg[i]));
    }

    // Configure auto-stop timer
    esp_timer_create_args_t timer_args = {
        .callback = &RobotController::OnStopTimer,
        .arg = this,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "robot_auto_stop",
        .skip_unhandled_events = false
    };
    ESP_ERROR_CHECK(esp_timer_create(&timer_args, &stop_timer_));

    Stop();
    RegisterMcpTools();
}

RobotController::~RobotController() {
    Stop();
    if (stop_timer_ != nullptr) {
        esp_timer_stop(stop_timer_);
        esp_timer_delete(stop_timer_);
        stop_timer_ = nullptr;
    }
}

void RobotController::SetCalibration(int8_t left_trim, int8_t right_trim, uint8_t min_pwm, uint8_t driver_type) {
    std::lock_guard<std::mutex> lock(mutex_);
    left_trim_ = left_trim;
    right_trim_ = right_trim;
    min_pwm_ = min_pwm;
    driver_type_ = driver_type;
    ESP_LOGI(TAG, "Calibration updated: LeftTrim=%d%%, RightTrim=%d%%, MinPWM=%d, DriverType=%d",
             left_trim_, right_trim_, min_pwm_, driver_type_);
}

void RobotController::OnStopTimer(void* arg) {
    RobotController* self = static_cast<RobotController*>(arg);
    ESP_LOGI(TAG, "Movement duration finished, stopping robot");
    self->Stop();
}

void RobotController::SetMotorOutputs(uint32_t in1, uint32_t in2, uint32_t in3, uint32_t in4) {
    ledc_set_duty(LEDC_SPEED_MODE, CH_LEFT_IN1, in1);
    ledc_update_duty(LEDC_SPEED_MODE, CH_LEFT_IN1);

    ledc_set_duty(LEDC_SPEED_MODE, CH_LEFT_IN2, in2);
    ledc_update_duty(LEDC_SPEED_MODE, CH_LEFT_IN2);

    ledc_set_duty(LEDC_SPEED_MODE, CH_RIGHT_IN3, in3);
    ledc_update_duty(LEDC_SPEED_MODE, CH_RIGHT_IN3);

    ledc_set_duty(LEDC_SPEED_MODE, CH_RIGHT_IN4, in4);
    ledc_update_duty(LEDC_SPEED_MODE, CH_RIGHT_IN4);
}

void RobotController::Stop() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (stop_timer_ != nullptr) {
        esp_timer_stop(stop_timer_);
    }
    if (routine_task_handle_ != nullptr) {
        vTaskDelete(routine_task_handle_);
        routine_task_handle_ = nullptr;
    }
    SetMotorOutputs(0, 0, 0, 0);
    current_direction_ = kDirectionStop;
    current_speed_ = 0;
    ESP_LOGI(TAG, "Robot stopped");
}

void RobotController::Move(Direction direction, int speed, int duration_ms) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (stop_timer_ != nullptr) {
        esp_timer_stop(stop_timer_);
    }

    speed = std::clamp(speed, 0, 100);
    current_direction_ = direction;
    current_speed_ = speed;

    if (speed == 0 || direction == kDirectionStop) {
        SetMotorOutputs(0, 0, 0, 0);
        return;
    }

    // Tính duty cho bánh trái và bánh phải kết hợp Trim & Min PWM
    auto calc_duty = [this](int base_speed, int8_t trim) -> uint32_t {
        if (base_speed <= 0) return 0;
        int eff = base_speed + (base_speed * trim / 100);
        eff = std::clamp(eff, 0, 100);
        if (eff == 0) return 0;
        uint32_t duty = min_pwm_ + ((255 - min_pwm_) * eff) / 100;
        return std::clamp<uint32_t>(duty, 0, 255);
    };

    uint32_t duty_left = calc_duty(speed, left_trim_);
    uint32_t duty_right = calc_duty(speed, right_trim_);

    switch (direction) {
        case kDirectionForward:
            // Bánh trái tiến: IN1=duty, IN2=0; Bánh phải tiến: IN3=duty, IN4=0
            SetMotorOutputs(duty_left, 0, duty_right, 0);
            ESP_LOGI(TAG, "Move FORWARD: L=%ld, R=%ld, dur=%dms", duty_left, duty_right, duration_ms);
            break;

        case kDirectionBackward:
            // Bánh trái lùi: IN1=0, IN2=duty; Bánh phải lùi: IN3=0, IN4=duty
            SetMotorOutputs(0, duty_left, 0, duty_right);
            ESP_LOGI(TAG, "Move BACKWARD: L=%ld, R=%ld, dur=%dms", duty_left, duty_right, duration_ms);
            break;

        case kDirectionTurnLeft:
            // Rẽ trái: Bánh trái dừng, bánh phải tiến
            SetMotorOutputs(0, 0, duty_right, 0);
            ESP_LOGI(TAG, "Move TURN LEFT: R=%ld, dur=%dms", duty_right, duration_ms);
            break;

        case kDirectionTurnRight:
            // Rẽ phải: Bánh trái tiến, bánh phải dừng
            SetMotorOutputs(duty_left, 0, 0, 0);
            ESP_LOGI(TAG, "Move TURN RIGHT: L=%ld, dur=%dms", duty_left, duration_ms);
            break;

        case kDirectionSpinLeft:
            // Xoay tròn sang trái: Trái lùi, Phải tiến
            SetMotorOutputs(0, duty_left, duty_right, 0);
            ESP_LOGI(TAG, "Move SPIN LEFT: L=%ld, R=%ld, dur=%dms", duty_left, duty_right, duration_ms);
            break;

        case kDirectionSpinRight:
            // Xoay tròn sang phải: Trái tiến, Phải lùi
            SetMotorOutputs(duty_left, 0, 0, duty_right);
            ESP_LOGI(TAG, "Move SPIN RIGHT: L=%ld, R=%ld, dur=%dms", duty_left, duty_right, duration_ms);
            break;

        case kDirectionCurveLeft:
            // Cong nhẹ sang trái: Trái chạy chậm hơn phải
            SetMotorOutputs(duty_left / 2, 0, duty_right, 0);
            break;

        case kDirectionCurveRight:
            // Cong nhẹ sang phải: Phải chạy chậm hơn trái
            SetMotorOutputs(duty_left, 0, duty_right / 2, 0);
            break;

        case kDirectionStop:
        default:
            SetMotorOutputs(0, 0, 0, 0);
            return;
    }

    if (duration_ms > 0 && stop_timer_ != nullptr) {
        esp_timer_start_once(stop_timer_, static_cast<uint64_t>(duration_ms) * 1000);
    }
}

void RobotController::Move(const std::string& direction_str, int speed, int duration_ms) {
    if (direction_str == "forward" || direction_str == "tien" || direction_str == "ahead") {
        Move(kDirectionForward, speed, duration_ms);
    } else if (direction_str == "backward" || direction_str == "lui" || direction_str == "back") {
        Move(kDirectionBackward, speed, duration_ms);
    } else if (direction_str == "left" || direction_str == "trai" || direction_str == "turn_left") {
        Move(kDirectionTurnLeft, speed, duration_ms);
    } else if (direction_str == "right" || direction_str == "phai" || direction_str == "turn_right") {
        Move(kDirectionTurnRight, speed, duration_ms);
    } else if (direction_str == "spin_left" || direction_str == "xoay_trai") {
        Move(kDirectionSpinLeft, speed, duration_ms);
    } else if (direction_str == "spin_right" || direction_str == "xoay_phai") {
        Move(kDirectionSpinRight, speed, duration_ms);
    } else if (direction_str == "curve_left") {
        Move(kDirectionCurveLeft, speed, duration_ms);
    } else if (direction_str == "curve_right") {
        Move(kDirectionCurveRight, speed, duration_ms);
    } else {
        Stop();
    }
}

// Routine: Lắc lư (Wiggle)
void RobotController::Wiggle() {
    Stop();
    xTaskCreate([](void* arg) {
        RobotController* self = static_cast<RobotController*>(arg);
        for (int i = 0; i < 4; i++) {
            self->Move(kDirectionSpinLeft, 70, 200);
            vTaskDelay(pdMS_TO_TICKS(220));
            self->Move(kDirectionSpinRight, 70, 200);
            vTaskDelay(pdMS_TO_TICKS(220));
        }
        self->Stop();
        vTaskDelete(NULL);
    }, "wiggle_task", 2048, this, 3, &routine_task_handle_);
}

// Routine: Nhảy múa (Dance)
void RobotController::Dance() {
    Stop();
    xTaskCreate([](void* arg) {
        RobotController* self = static_cast<RobotController*>(arg);
        // Bước 1: Tiến lùi nhanh
        self->Move(kDirectionForward, 75, 250);
        vTaskDelay(pdMS_TO_TICKS(300));
        self->Move(kDirectionBackward, 75, 250);
        vTaskDelay(pdMS_TO_TICKS(300));

        // Bước 2: Xoay vòng
        self->Move(kDirectionSpinLeft, 80, 500);
        vTaskDelay(pdMS_TO_TICKS(550));
        self->Move(kDirectionSpinRight, 80, 500);
        vTaskDelay(pdMS_TO_TICKS(550));

        // Bước 3: Lắc lư kết thúc
        for (int i = 0; i < 2; i++) {
            self->Move(kDirectionTurnLeft, 70, 180);
            vTaskDelay(pdMS_TO_TICKS(200));
            self->Move(kDirectionTurnRight, 70, 180);
            vTaskDelay(pdMS_TO_TICKS(200));
        }
        self->Stop();
        vTaskDelete(NULL);
    }, "dance_task", 2048, this, 3, &routine_task_handle_);
}

// Routine: Tự đi (Wander)
void RobotController::Wander() {
    Stop();
    xTaskCreate([](void* arg) {
        RobotController* self = static_cast<RobotController*>(arg);
        for (int i = 0; i < 5; i++) {
            self->Move(kDirectionForward, 70, 1200);
            vTaskDelay(pdMS_TO_TICKS(1300));
            // Rẽ ngẫu nhiên
            if (i % 2 == 0) {
                self->Move(kDirectionSpinLeft, 75, 400);
            } else {
                self->Move(kDirectionSpinRight, 75, 400);
            }
            vTaskDelay(pdMS_TO_TICKS(450));
        }
        self->Stop();
        vTaskDelete(NULL);
    }, "wander_task", 2048, this, 3, &routine_task_handle_);
}

std::string RobotController::GetStateJson() {
    std::string dir_str = "stop";
    switch (current_direction_) {
        case kDirectionForward: dir_str = "forward"; break;
        case kDirectionBackward: dir_str = "backward"; break;
        case kDirectionTurnLeft: dir_str = "turn_left"; break;
        case kDirectionTurnRight: dir_str = "turn_right"; break;
        case kDirectionSpinLeft: dir_str = "spin_left"; break;
        case kDirectionSpinRight: dir_str = "spin_right"; break;
        case kDirectionCurveLeft: dir_str = "curve_left"; break;
        case kDirectionCurveRight: dir_str = "curve_right"; break;
        default: dir_str = "stop"; break;
    }

    char buf[128];
    snprintf(buf, sizeof(buf), "{\"direction\":\"%s\",\"speed\":%d}", dir_str.c_str(), current_speed_);
    return std::string(buf);
}

void RobotController::RegisterMcpTools() {
    auto& mcp_server = McpServer::GetInstance();

    mcp_server.AddTool(
        "self.robot.move",
        "Dieu khien robot di chuyen theo huong (forward, backward, left, right, spin_left, spin_right, stop) voi toc do va thoi gian",
        PropertyList({
            Property("direction", kPropertyTypeString, std::string("forward")),
            Property("speed", kPropertyTypeInteger, 80, 10, 100),
            Property("duration_ms", kPropertyTypeInteger, 1000, 100, 10000)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            std::string dir = properties["direction"].value<std::string>();
            int speed = properties["speed"].value<int>();
            int duration = properties["duration_ms"].value<int>();
            Move(dir, speed, duration);
            return true;
        }
    );

    mcp_server.AddTool(
        "self.robot.forward",
        "Robot di thang ve phia truoc (tien len)",
        PropertyList({
            Property("duration_ms", kPropertyTypeInteger, 1000, 100, 10000),
            Property("speed", kPropertyTypeInteger, 80, 10, 100)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int duration = properties["duration_ms"].value<int>();
            int speed = properties["speed"].value<int>();
            Move(kDirectionForward, speed, duration);
            return true;
        }
    );

    mcp_server.AddTool(
        "self.robot.backward",
        "Robot lui ve phia sau",
        PropertyList({
            Property("duration_ms", kPropertyTypeInteger, 1000, 100, 10000),
            Property("speed", kPropertyTypeInteger, 80, 10, 100)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int duration = properties["duration_ms"].value<int>();
            int speed = properties["speed"].value<int>();
            Move(kDirectionBackward, speed, duration);
            return true;
        }
    );

    mcp_server.AddTool(
        "self.robot.turn_left",
        "Robot re sang ben trai",
        PropertyList({
            Property("duration_ms", kPropertyTypeInteger, 600, 100, 10000),
            Property("speed", kPropertyTypeInteger, 80, 10, 100)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int duration = properties["duration_ms"].value<int>();
            int speed = properties["speed"].value<int>();
            Move(kDirectionTurnLeft, speed, duration);
            return true;
        }
    );

    mcp_server.AddTool(
        "self.robot.turn_right",
        "Robot re sang ben phai",
        PropertyList({
            Property("duration_ms", kPropertyTypeInteger, 600, 100, 10000),
            Property("speed", kPropertyTypeInteger, 80, 10, 100)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int duration = properties["duration_ms"].value<int>();
            int speed = properties["speed"].value<int>();
            Move(kDirectionTurnRight, speed, duration);
            return true;
        }
    );

    mcp_server.AddTool(
        "self.robot.dance",
        "Robot bieu dien nhay mua vui nhon",
        PropertyList(),
        [this](const PropertyList& properties) -> ReturnValue {
            Dance();
            return true;
        }
    );

    mcp_server.AddTool(
        "self.robot.wiggle",
        "Robot lac lu sang hai ben",
        PropertyList(),
        [this](const PropertyList& properties) -> ReturnValue {
            Wiggle();
            return true;
        }
    );

    mcp_server.AddTool(
        "self.robot.stop",
        "Dung tat ca dong co robot ngay lap tuc",
        PropertyList(),
        [this](const PropertyList& properties) -> ReturnValue {
            Stop();
            return true;
        }
    );

    mcp_server.AddTool(
        "self.robot.get_state",
        "Lay trang thai di chuyen va toc do hien tai cua robot",
        PropertyList(),
        [this](const PropertyList& properties) -> ReturnValue {
            return GetStateJson();
        }
    );
}

