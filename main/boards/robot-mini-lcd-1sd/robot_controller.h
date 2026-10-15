#ifndef _ROBOT_CONTROLLER_H_
#define _ROBOT_CONTROLLER_H_

#include <string>
#include <driver/gpio.h>
#include <driver/ledc.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <mutex>

class RobotController {
public:
    enum Direction {
        kDirectionStop = 0,
        kDirectionForward,
        kDirectionBackward,
        kDirectionTurnLeft,
        kDirectionTurnRight,
        kDirectionSpinLeft,
        kDirectionSpinRight,
        kDirectionCurveLeft,
        kDirectionCurveRight
    };

    RobotController(gpio_num_t left_in1, gpio_num_t left_in2,
                    gpio_num_t right_in3, gpio_num_t right_in4);
    ~RobotController();

    void SetCalibration(int8_t left_trim, int8_t right_trim, uint8_t min_pwm, uint8_t driver_type);
    void Move(Direction direction, int speed, int duration_ms);
    void Move(const std::string& direction_str, int speed, int duration_ms);
    void Stop();

    void Wiggle();
    void Dance();
    void Wander();

    std::string GetStateJson();

private:
    gpio_num_t left_in1_;
    gpio_num_t left_in2_;
    gpio_num_t right_in3_;
    gpio_num_t right_in4_;

    int8_t left_trim_ = 0;
    int8_t right_trim_ = 0;
    uint8_t min_pwm_ = 20;
    uint8_t driver_type_ = 0;

    Direction current_direction_ = kDirectionStop;
    int current_speed_ = 0;
    std::mutex mutex_;
    esp_timer_handle_t stop_timer_ = nullptr;
    TaskHandle_t routine_task_handle_ = nullptr;

    void SetMotorOutputs(uint32_t in1, uint32_t in2, uint32_t in3, uint32_t in4);
    void RegisterMcpTools();
    static void OnStopTimer(void* arg);
    static void RoutineTask(void* arg);
};

#endif // _ROBOT_CONTROLLER_H_
