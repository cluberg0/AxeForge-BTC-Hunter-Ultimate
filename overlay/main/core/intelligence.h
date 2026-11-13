#pragma once
#include <stdint.h>
#include "esp_http_server.h"
namespace intel {
void start();
bool stable_point(uint16_t &f,uint16_t &mv,float &ghs);
// Runtime floor only. Does not change saved fan settings or override manual mode.
float fan_floor();
// Called ONLY by the original tuner, on an already failed locked window.
bool rollback_point(uint16_t current_f,uint16_t current_mv,uint16_t next_f,uint16_t cap,uint16_t &f,uint16_t &mv);
esp_err_t get(httpd_req_t *req);
esp_err_t set(httpd_req_t *req);
}
