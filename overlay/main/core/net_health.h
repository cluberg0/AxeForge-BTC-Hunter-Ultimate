#pragma once
#include <cstdint>
#include "esp_http_server.h"
namespace net_health {
enum class Error{Connect,Read,Write,Idle,Malformed};
void attempt(int pool);
void connected(int pool);
void disconnected(int pool);
void received(int pool,uint32_t bytes);
void processed(int pool,int64_t duration_us);
void error(int pool,Error what);
void selected(int pool);
bool active(int pool);
esp_err_t get(httpd_req_t*);
esp_err_t set(httpd_req_t*);
}
