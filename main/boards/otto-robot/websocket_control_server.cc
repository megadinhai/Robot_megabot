#include "websocket_control_server.h"
#include "web_admin_html.h"
#include "board.h"
#include "config.h"
#include "mcp_server.h"
#include "settings.h"
#include <wifi_manager.h>
#include <esp_log.h>
#include <esp_http_server.h>
#include <esp_timer.h>
#include <esp_system.h>
#include <sys/param.h>
#include <cstring>
#include <cstdlib>
#include <map>

static const char* TAG = "WSControl";

static void DispatchAction(const std::string& action_name, cJSON* args) {
    cJSON* req = cJSON_CreateObject();
    cJSON_AddStringToObject(req, "jsonrpc", "2.0");
    cJSON_AddStringToObject(req, "method", "tools/call");
    cJSON* params = cJSON_CreateObject();
    cJSON_AddStringToObject(params, "name", action_name.c_str());
    if (args != nullptr) {
        cJSON_AddItemToObject(params, "arguments", cJSON_Duplicate(args, 1));
    } else {
        cJSON_AddItemToObject(params, "arguments", cJSON_CreateObject());
    }
    cJSON_AddItemToObject(req, "params", params);
    cJSON_AddNumberToObject(req, "id", 1001);

    McpServer::GetInstance().ParseMessage(req);
    cJSON_Delete(req);
}

esp_err_t WebSocketControlServer::index_html_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, WEB_ADMIN_HTML, HTTPD_RESP_USE_STRLEN);
}

esp_err_t WebSocketControlServer::api_status_handler(httpd_req_t *req) {
    cJSON* res = cJSON_CreateObject();

    auto& wifi = WifiManager::GetInstance();
    cJSON_AddStringToObject(res, "ip", wifi.GetIpAddress().c_str());

    int level = 0;
    bool charging = false, discharging = false;
    Board::GetInstance().GetBatteryLevel(level, charging, discharging);
    cJSON_AddNumberToObject(res, "battery", level);
    cJSON_AddBoolToObject(res, "charging", charging);

    Settings server_settings("server", false);
    std::string server_type = server_settings.GetString("type", "megabot");
    std::string custom_url = server_settings.GetString("url", "wss://robot-megabot.onrender.com/ws/megabot");
    cJSON_AddStringToObject(res, "server_type", server_type.c_str());
    cJSON_AddStringToObject(res, "custom_ws_url", custom_url.c_str());

    Settings display_settings("display", false);
    bool swap_xy = display_settings.GetInt("swap_xy", DISPLAY_SWAP_XY ? 1 : 0) == 1;
    bool mirror_x = display_settings.GetInt("mirror_x", DISPLAY_MIRROR_X ? 1 : 0) == 1;
    bool mirror_y = display_settings.GetInt("mirror_y", DISPLAY_MIRROR_Y ? 1 : 0) == 1;
    cJSON_AddBoolToObject(res, "swap_xy", swap_xy);
    cJSON_AddBoolToObject(res, "mirror_x", mirror_x);
    cJSON_AddBoolToObject(res, "mirror_y", mirror_y);

    Settings trim_settings("otto_trims", false);
    cJSON* trims = cJSON_CreateObject();
    cJSON_AddNumberToObject(trims, "left_leg", trim_settings.GetInt("left_leg", 0));
    cJSON_AddNumberToObject(trims, "right_leg", trim_settings.GetInt("right_leg", 0));
    cJSON_AddNumberToObject(trims, "left_foot", trim_settings.GetInt("left_foot", 0));
    cJSON_AddNumberToObject(trims, "right_foot", trim_settings.GetInt("right_foot", 0));
    cJSON_AddNumberToObject(trims, "left_hand", trim_settings.GetInt("left_hand", 0));
    cJSON_AddNumberToObject(trims, "right_hand", trim_settings.GetInt("right_hand", 0));
    cJSON_AddItemToObject(res, "trims", trims);

    cJSON_AddNumberToObject(res, "free_heap", esp_get_free_heap_size());

    char* json_str = cJSON_PrintUnformatted(res);
    httpd_resp_set_type(req, "application/json; charset=utf-8");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    esp_err_t ret = httpd_resp_send(req, json_str, strlen(json_str));
    free(json_str);
    cJSON_Delete(res);
    return ret;
}

esp_err_t WebSocketControlServer::api_action_handler(httpd_req_t *req) {
    char buf[512];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    buf[ret] = '\0';
    cJSON* root = cJSON_Parse(buf);
    if (root != nullptr) {
        cJSON* act_item = cJSON_GetObjectItem(root, "action");
        if (cJSON_IsString(act_item)) {
            std::string act = act_item->valuestring;
            if (act == "walk") {
                DispatchAction("self.otto.walk", root);
            } else if (act == "turn") {
                DispatchAction("self.otto.turn", root);
            } else if (act == "jump") {
                DispatchAction("self.otto.jump", root);
            } else if (act == "swing") {
                DispatchAction("self.otto.swing", root);
            } else if (act == "moonwalk") {
                DispatchAction("self.otto.moonwalk", root);
            } else if (act == "hand_wave") {
                DispatchAction("self.otto.hand_wave", root);
            } else if (act == "sit") {
                DispatchAction("self.otto.sit", root);
            } else if (act == "dance") {
                DispatchAction("self.otto.magic_circle", root);
            } else if (act == "fitness") {
                DispatchAction("self.otto.fitness", root);
            } else if (act == "takeoff") {
                DispatchAction("self.otto.takeoff", root);
            } else if (act == "tiptoe_swing") {
                DispatchAction("self.otto.tiptoe_swing", root);
            } else if (act == "stop") {
                DispatchAction("self.otto.stop_and_home", nullptr);
            } else if (act == "home") {
                DispatchAction("self.otto.home", nullptr);
            } else {
                std::string tool_name = "self.otto." + act;
                DispatchAction(tool_name, root);
            }
        }
        cJSON_Delete(root);

        httpd_resp_set_type(req, "application/json");
        httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
        return httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);
    }
    httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON");
    return ESP_FAIL;
}

esp_err_t WebSocketControlServer::api_server_handler(httpd_req_t *req) {
    char buf[512];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    buf[ret] = '\0';
    cJSON* root = cJSON_Parse(buf);
    if (root != nullptr) {
        cJSON* type = cJSON_GetObjectItem(root, "server_type");
        cJSON* url = cJSON_GetObjectItem(root, "url");
        Settings server_settings("server", true);
        if (cJSON_IsString(type)) {
            server_settings.SetString("type", type->valuestring);
        }
        if (cJSON_IsString(url) && strlen(url->valuestring) > 0) {
            server_settings.SetString("url", url->valuestring);
        }
        cJSON_Delete(root);

        httpd_resp_set_type(req, "application/json");
        httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
        return httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);
    }
    httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON");
    return ESP_FAIL;
}

esp_err_t WebSocketControlServer::api_display_handler(httpd_req_t *req) {
    char buf[256];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    buf[ret] = '\0';
    cJSON* root = cJSON_Parse(buf);
    if (root != nullptr) {
        cJSON* swap_xy = cJSON_GetObjectItem(root, "swap_xy");
        cJSON* mirror_x = cJSON_GetObjectItem(root, "mirror_x");
        cJSON* mirror_y = cJSON_GetObjectItem(root, "mirror_y");
        Settings display_settings("display", true);
        if (cJSON_IsBool(swap_xy)) {
            display_settings.SetInt("swap_xy", cJSON_IsTrue(swap_xy) ? 1 : 0);
        }
        if (cJSON_IsBool(mirror_x)) {
            display_settings.SetInt("mirror_x", cJSON_IsTrue(mirror_x) ? 1 : 0);
        }
        if (cJSON_IsBool(mirror_y)) {
            display_settings.SetInt("mirror_y", cJSON_IsTrue(mirror_y) ? 1 : 0);
        }
        cJSON_Delete(root);

        httpd_resp_set_type(req, "application/json");
        httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
        return httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);
    }
    httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON");
    return ESP_FAIL;
}

esp_err_t WebSocketControlServer::api_trims_handler(httpd_req_t *req) {
    char buf[512];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }
    buf[ret] = '\0';
    cJSON* root = cJSON_Parse(buf);
    if (root != nullptr) {
        const char* servo_names[] = {"left_leg", "right_leg", "left_foot", "right_foot", "left_hand", "right_hand"};
        for (const char* name : servo_names) {
            cJSON* item = cJSON_GetObjectItem(root, name);
            if (cJSON_IsNumber(item)) {
                cJSON* args = cJSON_CreateObject();
                cJSON_AddStringToObject(args, "servo_type", name);
                cJSON_AddNumberToObject(args, "trim_value", item->valueint);
                DispatchAction("self.otto.set_trims", args);
                cJSON_Delete(args);
            }
        }
        cJSON_Delete(root);

        httpd_resp_set_type(req, "application/json");
        httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
        return httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);
    }
    httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON");
    return ESP_FAIL;
}

esp_err_t WebSocketControlServer::api_reboot_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_send(req, "{\"status\":\"rebooting\"}", HTTPD_RESP_USE_STRLEN);

    esp_timer_create_args_t timer_args = {
        .callback = [](void* arg) {
            esp_restart();
        },
        .arg = nullptr,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "reboot_timer"
    };
    esp_timer_handle_t timer;
    esp_timer_create(&timer_args, &timer);
    esp_timer_start_once(timer, 500000);
    return ESP_OK;
}

WebSocketControlServer* WebSocketControlServer::instance_ = nullptr;

WebSocketControlServer::WebSocketControlServer() : server_handle_(nullptr) {
    instance_ = this;
}

WebSocketControlServer::~WebSocketControlServer() {
    Stop();
    instance_ = nullptr;
}

esp_err_t WebSocketControlServer::ws_handler(httpd_req_t *req) {
    if (instance_ == nullptr) {
        return ESP_FAIL;
    }
    
    if (req->method == HTTP_GET) {
        ESP_LOGI(TAG, "Handshake done, the new connection was opened");
        instance_->AddClient(req);
        return ESP_OK;
    }
    
    httpd_ws_frame_t ws_pkt;
    uint8_t *buf = NULL;
    memset(&ws_pkt, 0, sizeof(httpd_ws_frame_t));
    ws_pkt.type = HTTPD_WS_TYPE_TEXT;
    
    /* Set max_len = 0 to get the frame len */
    esp_err_t ret = httpd_ws_recv_frame(req, &ws_pkt, 0);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "httpd_ws_recv_frame failed to get frame len with %d", ret);
        return ret;
    }
    ESP_LOGI(TAG, "frame len is %d", ws_pkt.len);
    
    if (ws_pkt.len) {
        /* ws_pkt.len + 1 is for NULL termination as we are expecting a string */
        buf = (uint8_t*)calloc(1, ws_pkt.len + 1);
        if (buf == NULL) {
            ESP_LOGE(TAG, "Failed to calloc memory for buf");
            return ESP_ERR_NO_MEM;
        }
        ws_pkt.payload = buf;
        /* Set max_len = ws_pkt.len to get the frame payload */
        ret = httpd_ws_recv_frame(req, &ws_pkt, ws_pkt.len);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "httpd_ws_recv_frame failed with %d", ret);
            free(buf);
            return ret;
        }
        ESP_LOGI(TAG, "Got packet with message: %s", ws_pkt.payload);
    }
    
    ESP_LOGI(TAG, "Packet type: %d", ws_pkt.type);
    
    if (ws_pkt.type == HTTPD_WS_TYPE_CLOSE) {
        ESP_LOGI(TAG, "WebSocket close frame received");
        instance_->RemoveClient(req);
        free(buf);
        return ESP_OK;
    }
    
    if (ws_pkt.type == HTTPD_WS_TYPE_TEXT) {
        if (ws_pkt.len > 0 && buf != nullptr) {
            buf[ws_pkt.len] = '\0';
            instance_->HandleMessage(req, (const char*)buf, ws_pkt.len);
        }
    } else {
        ESP_LOGW(TAG, "Unsupported frame type: %d", ws_pkt.type);
    }
    
    free(buf);
    return ESP_OK;
}

bool WebSocketControlServer::Start(int port) {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = port;
    config.max_open_sockets = 7;
    config.ctrl_port = 32769;
    config.stack_size = 10240;

    httpd_uri_t ws_uri = {
        .uri = "/ws",
        .method = HTTP_GET,
        .handler = ws_handler,
        .user_ctx = nullptr,
        .is_websocket = true
    };

    httpd_uri_t index_uri = {
        .uri = "/",
        .method = HTTP_GET,
        .handler = index_html_handler,
        .user_ctx = nullptr
    };

    httpd_uri_t index_html_uri = {
        .uri = "/index.html",
        .method = HTTP_GET,
        .handler = index_html_handler,
        .user_ctx = nullptr
    };

    httpd_uri_t status_uri = {
        .uri = "/api/status",
        .method = HTTP_GET,
        .handler = api_status_handler,
        .user_ctx = nullptr
    };

    httpd_uri_t action_uri = {
        .uri = "/api/action",
        .method = HTTP_POST,
        .handler = api_action_handler,
        .user_ctx = nullptr
    };

    httpd_uri_t server_uri = {
        .uri = "/api/server",
        .method = HTTP_POST,
        .handler = api_server_handler,
        .user_ctx = nullptr
    };

    httpd_uri_t display_uri = {
        .uri = "/api/display",
        .method = HTTP_POST,
        .handler = api_display_handler,
        .user_ctx = nullptr
    };

    httpd_uri_t trims_uri = {
        .uri = "/api/trims",
        .method = HTTP_POST,
        .handler = api_trims_handler,
        .user_ctx = nullptr
    };

    httpd_uri_t reboot_uri = {
        .uri = "/api/reboot",
        .method = HTTP_POST,
        .handler = api_reboot_handler,
        .user_ctx = nullptr
    };

    if (httpd_start(&server_handle_, &config) == ESP_OK) {
        httpd_register_uri_handler(server_handle_, &ws_uri);
        httpd_register_uri_handler(server_handle_, &index_uri);
        httpd_register_uri_handler(server_handle_, &index_html_uri);
        httpd_register_uri_handler(server_handle_, &status_uri);
        httpd_register_uri_handler(server_handle_, &action_uri);
        httpd_register_uri_handler(server_handle_, &server_uri);
        httpd_register_uri_handler(server_handle_, &display_uri);
        httpd_register_uri_handler(server_handle_, &trims_uri);
        httpd_register_uri_handler(server_handle_, &reboot_uri);
        ESP_LOGI(TAG, "WebSocket & Web Admin server started on port %d", port);
        return true;
    }

    ESP_LOGE(TAG, "Failed to start HTTP/WebSocket server");
    return false;
}

void WebSocketControlServer::Stop() {
    if (server_handle_) {
        httpd_stop(server_handle_);
        server_handle_ = nullptr;
        clients_.clear();
        ESP_LOGI(TAG, "WebSocket server stopped");
    }
}

void WebSocketControlServer::HandleMessage(httpd_req_t *req, const char* data, size_t len) {
    if (data == nullptr || len == 0) {
        ESP_LOGE(TAG, "Invalid message: data is null or len is 0");
        return;
    }
    
    if (len > 4096) {
        ESP_LOGE(TAG, "Message too long: %zu bytes", len);
        return;
    }
    
    char* temp_buf = (char*)malloc(len + 1);
    if (temp_buf == nullptr) {
        ESP_LOGE(TAG, "Failed to allocate memory");
        return;
    }
    memcpy(temp_buf, data, len);
    temp_buf[len] = '\0';
    
    cJSON* root = cJSON_Parse(temp_buf);
    free(temp_buf);
    
    if (root == nullptr) {
        ESP_LOGE(TAG, "Failed to parse JSON");
        return;
    }

    int sock_fd = httpd_req_to_sockfd(req);
    uint64_t client_id = GetClientId(req);
    if (client_id == 0) {
        ESP_LOGW(TAG, "Ignoring message from unknown client: %d", sock_fd);
        cJSON_Delete(root);
        return;
    }

    auto response_sender = [sock_fd, client_id](const std::string& payload) {
        if (WebSocketControlServer::instance_) {
            WebSocketControlServer::instance_->SendMessage(sock_fd, client_id, payload);
        }
    };

    // 支持两种格式：
    // 1. 完整格式：{"type":"mcp","payload":{...}}
    // 2. 简化格式：直接是MCP payload对象
    
    cJSON* payload = nullptr;
    cJSON* type = cJSON_GetObjectItem(root, "type");
    
    if (type && cJSON_IsString(type) && strcmp(type->valuestring, "mcp") == 0) {
        payload = cJSON_GetObjectItem(root, "payload");
        if (payload != nullptr) {
            cJSON_DetachItemViaPointer(root, payload);
            McpServer::GetInstance().ParseMessage(payload, response_sender);
            cJSON_Delete(payload); 
        }
    } else {
        payload = cJSON_Duplicate(root, 1);
        if (payload != nullptr) {
            McpServer::GetInstance().ParseMessage(payload, response_sender);
            cJSON_Delete(payload);
        }
    }
    
    if (payload == nullptr) {
        ESP_LOGE(TAG, "Invalid message format or failed to parse");
    }

    cJSON_Delete(root);
}

void WebSocketControlServer::AddClient(httpd_req_t *req) {
    int sock_fd = httpd_req_to_sockfd(req);
    if (clients_.find(sock_fd) == clients_.end()) {
        uint64_t client_id = ++next_client_id_;
        clients_[sock_fd] = ClientInfo{
            .client_id = client_id
        };
        ESP_LOGI(TAG, "Client connected: %d id=%llu (total: %zu)", sock_fd, (unsigned long long)client_id, clients_.size());
    }
}

void WebSocketControlServer::RemoveClient(httpd_req_t *req) {
    int sock_fd = httpd_req_to_sockfd(req);
    clients_.erase(sock_fd);
    ESP_LOGI(TAG, "Client disconnected: %d (total: %zu)", sock_fd, clients_.size());
}

size_t WebSocketControlServer::GetClientCount() const {
    return clients_.size();
}

uint64_t WebSocketControlServer::GetClientId(httpd_req_t *req) const {
    int sock_fd = httpd_req_to_sockfd(req);
    auto it = clients_.find(sock_fd);
    if (it == clients_.end()) {
        return 0;
    }
    return it->second.client_id;
}

struct WsBroadcastJob {
    httpd_handle_t server;
    int fd;
    char* payload;
    size_t len;
};

static void ws_broadcast_send_job(void* arg) {
    WsBroadcastJob* job = static_cast<WsBroadcastJob*>(arg);

    httpd_ws_frame_t ws_pkt = {};
    ws_pkt.type = HTTPD_WS_TYPE_TEXT;
    ws_pkt.payload = reinterpret_cast<uint8_t*>(job->payload);
    ws_pkt.len = job->len;
    ws_pkt.final = true;

    esp_err_t ret = httpd_ws_send_frame_async(job->server, job->fd, &ws_pkt);
    if (ret != ESP_OK) {
        ESP_LOGE("WSControl", "BroadcastMessage: send failed fd=%d err=%d", job->fd, ret);
    }

    free(job->payload);
    free(job);
}

void WebSocketControlServer::BroadcastMessage(const std::string& message) {
    if (!server_handle_ || clients_.empty()) {
        return;
    }

    for (auto& [fd, client] : clients_) {
        SendMessage(fd, client.client_id, message);
    }
}

void WebSocketControlServer::SendMessage(int sock_fd, uint64_t client_id, const std::string& message) {
    if (!server_handle_) {
        return;
    }

    auto client = clients_.find(sock_fd);
    if (client == clients_.end() || client->second.client_id != client_id) {
        ESP_LOGW(TAG, "Skip send to stale client fd=%d id=%llu", sock_fd, (unsigned long long)client_id);
        return;
    }

    WsBroadcastJob* job = static_cast<WsBroadcastJob*>(malloc(sizeof(WsBroadcastJob)));
    if (!job) {
        ESP_LOGE(TAG, "SendMessage: failed to allocate job");
        return;
    }

    job->server = server_handle_;
    job->fd = sock_fd;
    job->len = message.length();
    job->payload = static_cast<char*>(malloc(message.length() + 1));
    if (!job->payload) {
        ESP_LOGE(TAG, "SendMessage: failed to allocate payload");
        free(job);
        return;
    }
    memcpy(job->payload, message.c_str(), message.length());
    job->payload[message.length()] = '\0';

    esp_err_t ret = httpd_queue_work(server_handle_, ws_broadcast_send_job, job);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SendMessage: httpd_queue_work failed fd=%d err=%d", sock_fd, ret);
        free(job->payload);
        free(job);
    }
}
