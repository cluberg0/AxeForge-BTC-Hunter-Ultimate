#pragma once
#include <cstddef>
using esp_http_client_handle_t = void*;
using esp_err_t = int;
struct esp_http_client_config_t {
 const char *url = nullptr;
 esp_err_t (*crt_bundle_attach)(void*) = nullptr;
 bool disable_auto_redirect = false;
 int timeout_ms = 0;
 int buffer_size = 0;
};
esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t*);
int esp_http_client_open(esp_http_client_handle_t, int);
int esp_http_client_fetch_headers(esp_http_client_handle_t);
int esp_http_client_get_status_code(esp_http_client_handle_t);
int esp_http_client_read(esp_http_client_handle_t,char*,int);
bool esp_http_client_is_complete_data_received(esp_http_client_handle_t);
int esp_http_client_cleanup(esp_http_client_handle_t);
