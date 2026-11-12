#include "guardian.h"
#include "core/hunter.h"
#include "core/json_util.h"
#include "core/state.h"
#include "net/wifi.h"
#include "net/notify.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/idf_additions.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "nvs.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <ctime>

namespace guardian {
namespace {
// Only Bitcoin mainnet, with certificate validation and no redirects. An
// explorer is a third-party observation, not our own consensus validation.
constexpr const char *BASE = "https://mempool.space/api/block/";
constexpr int64_t DAY_US = 86400000000LL;
struct Observation {
    bool enabled = false;
    uint8_t state = 5;  // none, pending, not found, observed, error, disabled
    char hash[65] = {};
    uint32_t checked = 0;
    uint32_t height = 0;
    bool in_best_chain = false;
    const char *error = "";  // fixed local codes only; never remote/user strings
};
Observation status;
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
SemaphoreHandle_t config_lock = nullptr;
bool task_ok = false;
uint32_t epoch = 0;
int64_t next_query = 0, window_start = 0;

bool valid_hash(const char *hash)
{
    if (!hash || strlen(hash) != 64) return false;
    for (unsigned i = 0; i < 64; ++i)
        if (!((hash[i] >= '0' && hash[i] <= '9') ||
              (hash[i] >= 'a' && hash[i] <= 'f') ||
              (hash[i] >= 'A' && hash[i] <= 'F'))) return false;
    return true;
}

Observation query(const char *hash)
{
    Observation out;
    out.state = 4;
    out.error = "tls_http";
    out.checked = uint32_t(time(nullptr));
    memcpy(out.hash, hash, 65);
    char url[128];
    snprintf(url, sizeof(url), "%s%s/status", BASE, hash);
    esp_http_client_config_t cfg = {};
    cfg.url = url;
    cfg.crt_bundle_attach = esp_crt_bundle_attach;
    cfg.disable_auto_redirect = true;
    cfg.timeout_ms = 4000;
    cfg.buffer_size = 1024;
    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (!client) { out.error = "no_memory"; return out; }
    // Bounded payload and elapsed-time budget even for a stalled/chunked peer.
    char body[512];
    size_t size = 0;
    bool complete = false, read_failed = false;
    int64_t deadline = esp_timer_get_time() + 15000000LL;
    if (esp_http_client_open(client, 0) == ESP_OK) {
        esp_http_client_fetch_headers(client);
        int code = esp_http_client_get_status_code(client);
        if (code == 404) {
            out.state = 2;
            out.error = "";
        } else if (code == 200) {
            while (size < sizeof(body) - 1 && esp_timer_get_time() < deadline) {
                int n = esp_http_client_read(client, body + size, int(sizeof(body) - 1 - size));
                if (n <= 0) {
                    read_failed = n < 0;
                    complete = n == 0 && esp_http_client_is_complete_data_received(client);
                    break;
                }
                size += unsigned(n);
            }
            if (!complete && !read_failed && size < sizeof(body) - 1)
                complete = esp_http_client_is_complete_data_received(client);
            if (complete) {
                body[size] = 0;
                cJSON *json = json_parse(body);
                cJSON *chain = json ? cJSON_GetObjectItem(json, "in_best_chain") : nullptr;
                cJSON *height = json ? cJSON_GetObjectItem(json, "height") : nullptr;
                bool in_chain = cJSON_IsTrue(chain);
                bool height_ok = cJSON_IsNumber(height) && std::isfinite(height->valuedouble) &&
                                 height->valuedouble >= 0 && height->valuedouble <= 2147483647. &&
                                 std::floor(height->valuedouble) == height->valuedouble;
                if (cJSON_IsBool(chain) && (!in_chain || height_ok)) {
                    out.state = 3;
                    out.error = "";
                    out.in_best_chain = in_chain;
                    out.height = height_ok ? uint32_t(height->valuedouble) : 0;
                } else out.error = "invalid_response";
                cJSON_Delete(json);
            } else out.error = "incomplete_response";
        }
    }
    esp_http_client_cleanup(client);
    return out;
}

void tick()
{
    Observation before;
    uint32_t generation;
    portENTER_CRITICAL(&mux);
    before = status;
    generation = epoch;
    portEXIT_CRITICAL(&mux);
    if (!before.enabled) return;
    char hash[65];
    int pool = -1;
    if (!hunter::candidate_snapshot(hash, pool) || !valid_hash(hash)) return;
    int64_t now = esp_timer_get_time();
    portENTER_CRITICAL(&mux);
    if (!status.enabled || generation != epoch) {
        portEXIT_CRITICAL(&mux);
        return;
    }
    if (strcmp(status.hash, hash) != 0) {
        status = Observation{};
        status.enabled = true;
        status.state = 1;
        memcpy(status.hash, hash, sizeof(hash));
        window_start = now;
        next_query = 0;
    }
    before = status;
    if (now < next_query) {
        portEXIT_CRITICAL(&mux);
        return;
    }
    if (now - window_start >= DAY_US) {
        status.state = 4;
        status.in_best_chain = false;
        status.height = 0;
        status.error = "expired";
        portEXIT_CRITICAL(&mux);
        return;
    }
    next_query = now + (now - window_start < 3600000000LL ? 60000000LL : 300000000LL);
    portEXIT_CRITICAL(&mux);

    Observation next = before;
    if (!wifi::connected()) { next.state = 4; next.error = "offline"; }
    else if (!g_state.time_synced) { next.state = 4; next.error = "time_unsynced"; }
    else next = query(hash);

    char current_hash[65];
    int current_pool = -1;
    if (!hunter::candidate_snapshot(current_hash, current_pool) || strcmp(current_hash, hash) != 0) return;
    if (next.state != 3) { next.in_best_chain = false; next.height = 0; }
    bool announce = false;
    portENTER_CRITICAL(&mux);
    // Disabling during HTTPS or a newer candidate must invalidate that result.
    if (status.enabled && epoch == generation && strcmp(status.hash, hash) == 0) {
        next.enabled = true;
        announce = next.state == 3 && next.in_best_chain &&
                   (status.state != 3 || !status.in_best_chain);
        status = next;
    }
    portEXIT_CRITICAL(&mux);
    if (announce)
        notify::post(NOTIFY_BLOCK, "EXPLORER mempool.space observes %s at height %lu on best chain (not reward proof)",
                     hash, (unsigned long)next.height);
}

void task(void *)
{
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        tick();
    }
}
}

void start()
{
    config_lock = xSemaphoreCreateMutex();
    if (!config_lock) return;
    nvs_handle_t handle;
    if (nvs_open("af_guardian", NVS_READONLY, &handle) == ESP_OK) {
        uint8_t saved[2] = {};
        size_t size = sizeof(saved);
        if (nvs_get_blob(handle, "config", saved, &size) == ESP_OK && size == sizeof(saved) &&
            saved[0] == 1 && saved[1] <= 1) {
            status.enabled = saved[1] != 0;
            status.state = status.enabled ? 0 : 5;
        }
        nvs_close(handle);
    }
    // Network-only task: no flash writes. Stock HTTP tasks also use PSRAM stacks.
    task_ok = xTaskCreatePinnedToCoreWithCaps(task, "block_guardian", 8192, nullptr, 2,
                                             nullptr, tskNO_AFFINITY, MALLOC_CAP_SPIRAM) == pdPASS;
    if (!task_ok && status.enabled) { status.state = 4; status.error = "task_unavailable"; }
}

esp_err_t get(httpd_req_t *req)
{
    Observation copy;
    portENTER_CRITICAL(&mux);
    copy = status;
    portEXIT_CRITICAL(&mux);
    char body[384];
    snprintf(body, sizeof(body),
             "{\"enabled\":%s,\"taskOk\":%s,\"state\":%u,\"hash\":\"%s\",\"checked\":%lu,\"height\":%lu,\"inBestChain\":%s,\"error\":\"%s\"}",
             copy.enabled ? "true" : "false", task_ok ? "true" : "false", unsigned(copy.state),
             copy.hash, (unsigned long)copy.checked, (unsigned long)copy.height,
             copy.in_best_chain ? "true" : "false", copy.error);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    return httpd_resp_sendstr(req, body);
}

esp_err_t set(httpd_req_t *req)
{
    if (!task_ok || !config_lock)
        return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "guardian task unavailable");
    char body[96];
    if (req->content_len <= 0 || unsigned(req->content_len) >= sizeof(body))
        return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "bad body");
    int size = 0;
    while (size < req->content_len) {
        int n = httpd_req_recv(req, body + size, req->content_len - size);
        if (n <= 0) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "incomplete body");
        size += n;
    }
    body[size] = 0;
    cJSON *json = json_parse(body);
    cJSON *flag = json ? cJSON_GetObjectItem(json, "enabled") : nullptr;
    bool valid = cJSON_IsBool(flag), enabled = cJSON_IsTrue(flag);
    cJSON_Delete(json);
    if (!valid) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "enabled bool required");
    if (xSemaphoreTake(config_lock, pdMS_TO_TICKS(100)) != pdTRUE)
        return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "settings busy");
    nvs_handle_t handle;
    bool good = false;
    if (nvs_open("af_guardian", NVS_READWRITE, &handle) == ESP_OK) {
        uint8_t saved[2] = {1, uint8_t(enabled)};
        good = nvs_set_blob(handle, "config", saved, sizeof(saved)) == ESP_OK && nvs_commit(handle) == ESP_OK;
        nvs_close(handle);
    }
    if (good) {
        portENTER_CRITICAL(&mux);
        ++epoch;
        status = Observation{};
        status.enabled = enabled;
        status.state = enabled ? 0 : 5;
        next_query = window_start = 0;
        portEXIT_CRITICAL(&mux);
    }
    xSemaphoreGive(config_lock);
    if (!good) return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "settings write failed");
    return httpd_resp_sendstr(req, "OK");
}
}
