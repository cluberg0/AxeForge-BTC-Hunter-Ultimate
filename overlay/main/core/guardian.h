#pragma once
#include "esp_http_server.h"

// Optional, independent explorer observation. Never part of candidate submission.
namespace guardian {
void start();
esp_err_t get(httpd_req_t *req);
esp_err_t set(httpd_req_t *req);
}
