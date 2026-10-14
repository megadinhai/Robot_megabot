#ifndef _ROBOT_ADMIN_SERVER_H_
#define _ROBOT_ADMIN_SERVER_H_

#include <esp_http_server.h>
#include "pin_config.h"
#include "robot_controller.h"

class RobotAdminServer {
public:
    RobotAdminServer(RobotPinConfig& pin_cfg, RobotCalibration& calib, RobotController* controller);
    ~RobotAdminServer();

    bool Start(int port = 8080);
    void Stop();

private:
    httpd_handle_t server_ = nullptr;
    RobotPinConfig& pin_cfg_;
    RobotCalibration& calib_;
    RobotController* controller_;

    static esp_err_t RootGetHandler(httpd_req_t *req);
    static esp_err_t ConfigGetHandler(httpd_req_t *req);
    static esp_err_t ConfigPostHandler(httpd_req_t *req);
    static esp_err_t MotorCalibPostHandler(httpd_req_t *req);
    static esp_err_t ControlPostHandler(httpd_req_t *req);
    static esp_err_t ResetPostHandler(httpd_req_t *req);
    static esp_err_t RebootPostHandler(httpd_req_t *req);
};

#endif // _ROBOT_ADMIN_SERVER_H_

