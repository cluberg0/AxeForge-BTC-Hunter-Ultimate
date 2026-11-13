#include <cassert>
#include <cstring>
#include <vector>
#include <cstdio>
#include "esp_http_server.h"
#include "../overlay/main/net/weather.cpp"
#include "../overlay/main/net/mempool.cpp"
State g_state{};static bool fail=false,mutex_fail=false,task_fail=false;static int tasks=0,writes=0,ntp=0,servers=0;static std::vector<unsigned char> saved;static void(*callback)(struct timeval*)=nullptr;struct Deleted{};
void esp_sntp_setoperatingmode(int x){assert(x==SNTP_OPMODE_POLL);}void esp_sntp_setservername(int,const char*){servers++;}void sntp_set_time_sync_notification_cb(void(*fn)(struct timeval*)){callback=fn;}void esp_sntp_init(){ntp++;}
namespace wifi{bool connected(){return true;}}
void vTaskDelay(unsigned){}void vTaskDelete(void*){throw Deleted{};}int xTaskCreate(void(*)(void*),const char*,unsigned,void*,int,void*){tasks++;return task_fail?0:pdPASS;}
SemaphoreHandle_t xSemaphoreCreateMutex(){return mutex_fail?nullptr:reinterpret_cast<void*>(1);}int xSemaphoreTake(SemaphoreHandle_t,unsigned){return pdTRUE;}int xSemaphoreGive(SemaphoreHandle_t){return pdTRUE;}
int nvs_open(const char*ns,int,nvs_handle_t*h){assert(!strcmp(ns,"af_clock"));*h=1;return ESP_OK;}int nvs_get_blob(nvs_handle_t,const char*,void*p,size_t*n){if(saved.size()!=*n)return ESP_FAIL;memcpy(p,saved.data(),*n);return ESP_OK;}int nvs_set_blob(nvs_handle_t,const char*,const void*p,size_t n){writes++;if(fail)return ESP_FAIL;auto*a=static_cast<const unsigned char*>(p);saved={a,a+n};return ESP_OK;}int nvs_commit(nvs_handle_t){return fail?ESP_FAIL:ESP_OK;}void nvs_close(nvs_handle_t){}
int main(){weather::start();assert(tasks==1&&!g_state.weather.valid&&!g_state.time_synced);try{clock_task(nullptr);assert(false);}catch(Deleted&){}assert(servers==2&&ntp==1&&callback);callback(nullptr);assert(g_state.time_synced);assert(weather::set_offset_minutes(600));int n=writes;assert(weather::set_offset_minutes(600)&&writes==n);assert(!weather::set_offset_minutes(841));fail=true;assert(!weather::set_offset_minutes(0)&&weather::offset_minutes()==600);fail=false;offset=0;weather::start();assert(weather::offset_minutes()==600);mutex_fail=true;weather::start();assert(!weather::set_offset_minutes(0));n=tasks;weather::refresh_now();mempool::start();mempool::refresh_now();assert(tasks==n&&!g_state.mempool.valid);puts("PASS NTP retained/self-terminating init, persisted/manual UTC, NVS/mutex failures, Weather/Mempool refresh creates no tasks or HTTP");}
