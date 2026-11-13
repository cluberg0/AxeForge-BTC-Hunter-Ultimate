#include "weather.h"
#include "core/state.h"
#include "esp_sntp.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "net/wifi.h"
#include "nvs.h"
#include <atomic>
#include <cstdio>
namespace {
std::atomic<int> offset{0};
SemaphoreHandle_t config_lock=nullptr;
struct ClockConfig{uint32_t magic=0x434c4b32;int32_t minutes=0;};
void synced(struct timeval*){g_state.time_synced=true;ESP_LOGI("clock","NTP time synced");}
void clock_task(void*){
 while(!wifi::connected())vTaskDelay(pdMS_TO_TICKS(1000));
 esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
 esp_sntp_setservername(0,"pool.ntp.org");esp_sntp_setservername(1,"time.google.com");
 sntp_set_time_sync_notification_cb(synced);esp_sntp_init();
 vTaskDelete(nullptr); // SNTP maintains time; no forecast task, retries or TLS
}
}
namespace weather {
void start(){
 config_lock=xSemaphoreCreateMutex();
 nvs_handle_t h;if(nvs_open("af_clock",NVS_READONLY,&h)==ESP_OK){ClockConfig c;size_t n=sizeof(c);if(nvs_get_blob(h,"offset",&c,&n)==ESP_OK&&n==sizeof(c)&&c.magic==0x434c4b32&&c.minutes>=-720&&c.minutes<=840)offset=c.minutes;nvs_close(h);}
 g_state.weather.valid=false;g_state.weather.utc_offset_s=offset.load()*60;
 snprintf(g_state.weather.error,sizeof(g_state.weather.error),"Weather disabled; clock uses manual UTC offset");
 if(xTaskCreate(clock_task,"ntp_init",3072,nullptr,2,nullptr)!=pdPASS)ESP_LOGE("clock","NTP init task unavailable");
}
void refresh_now(){} // compatibility: city changes never open HTTP/TLS
bool local_time(struct tm*out){if(!g_state.time_synced)return false;time_t now=time(nullptr)+offset.load()*60;return gmtime_r(&now,out)!=nullptr;}
const char*describe(int){return "Disabled";}
int offset_minutes(){return offset.load();}
bool set_offset_minutes(int value){
 if(value< -720||value>840||!config_lock||xSemaphoreTake(config_lock,pdMS_TO_TICKS(100))!=pdTRUE)return false;
 bool good=value==offset.load();
 if(!good){nvs_handle_t h;if(nvs_open("af_clock",NVS_READWRITE,&h)==ESP_OK){ClockConfig c;c.minutes=value;good=nvs_set_blob(h,"offset",&c,sizeof(c))==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);}}
 if(good){offset=value;g_state.weather.utc_offset_s=value*60;}
 xSemaphoreGive(config_lock);return good;
}
}
