#include <cassert>
#include <cstring>
#include <iostream>
#include <map>
#include <string>
#include <vector>
#include "../overlay/main/core/intelligence.cpp"
MinerState g_state{};
static Settings cfg{};
namespace settings {Settings &get(){return cfg;}}
static bool locked=false,deny_lock=false,storage_fail=false;
static size_t available=1000;
static std::map<std::string,std::vector<unsigned char>> blobs;
SemaphoreHandle_t xSemaphoreCreateMutex(){return reinterpret_cast<void*>(1);}
int xSemaphoreTake(SemaphoreHandle_t,unsigned){if(locked||deny_lock)return 0;locked=true;return pdTRUE;}
int xSemaphoreGive(SemaphoreHandle_t){assert(locked);locked=false;return pdTRUE;}
void vTaskDelay(unsigned){}
int xTaskCreate(void(*)(void*),const char*,unsigned,void*,int,void*){return pdPASS;}
int nvs_get_stats(const char*,nvs_stats_t*s){*s={0,available,1000,1};return ESP_OK;}
int nvs_open(const char*,int,nvs_handle_t*h){*h=1;return ESP_OK;}
int nvs_get_blob(nvs_handle_t,const char*k,void*p,size_t*n){auto i=blobs.find(k);if(i==blobs.end()||i->second.size()!=*n)return ESP_FAIL;memcpy(p,i->second.data(),*n);return ESP_OK;}
int nvs_set_blob(nvs_handle_t,const char*k,const void*p,size_t n){if(storage_fail)return ESP_FAIL;auto*b=static_cast<const unsigned char*>(p);blobs[k]={b,b+n};return ESP_OK;}
int nvs_commit(nvs_handle_t){return storage_fail?ESP_FAIL:ESP_OK;}
void nvs_close(nvs_handle_t){}
static std::string response,body;
static cJSON root{},on{1,1},restore{1,1},array{},curve[4]={{50,50},{55,55},{75,75},{100,100}};
cJSON*cJSON_Parse(const char*s){return std::string(s)=="valid"?&root:nullptr;}
cJSON*cJSON_GetObjectItem(cJSON*,const char*k){if(!strcmp(k,"enabled"))return &on;if(!strcmp(k,"restore"))return &restore;return &array;}
cJSON*cJSON_GetArrayItem(cJSON*,int i){return &curve[i];}
bool cJSON_IsBool(cJSON*p){return p==&on||p==&restore;}
bool cJSON_IsArray(cJSON*p){return p==&array;}
bool cJSON_IsTrue(cJSON*p){return p->valueint==1;}
bool cJSON_IsNumber(cJSON*p){return p>=curve&&p<curve+4;}
int cJSON_GetArraySize(cJSON*){return 4;}
void cJSON_Delete(cJSON*){}
int httpd_resp_send_chunk(httpd_req_t*,const char*s,int n){if(s)response.append(s,n);return ESP_OK;}
int httpd_resp_send_err(httpd_req_t*,int code,const char*s){response=s;return code;}
int httpd_resp_sendstr(httpd_req_t*,const char*s){response=s;return ESP_OK;}
int httpd_req_get_url_query_str(httpd_req_t*,char*,size_t){return ESP_FAIL;}
int httpd_query_key_value(const char*,const char*,char*,size_t){return ESP_FAIL;}
int httpd_resp_set_type(httpd_req_t*,const char*){return ESP_OK;}
int httpd_resp_set_hdr(httpd_req_t*,const char*,const char*){return ESP_OK;}
int httpd_req_recv(httpd_req_t*,char*p,size_t n){memcpy(p,body.data(),n);return int(n);}
static int set_config(){body="valid";httpd_req_t r{int(body.size())};return intel::set(&r);}
int main(){
 (void)TAG;
 intel::start();assert(task_ok&&mu&&save_day&&save_month);assert(!conf.enabled&&!conf.restore);
 g_state.status=SysStatus::Mining;g_state.time_synced=g_state.temp_ok=g_state.vr_temp_ok=g_state.pool_connected=g_state.fan_present[0]=true;
 g_state.hashrate_ghs=1550;g_state.expected_ghs=1600;g_state.chip_temp_max=55;g_state.vr_temp=64;g_state.pin=23;g_state.error_pct=.3;g_state.vin=5.1;g_state.vout=1.17;g_state.fan_rpm[0]=5000;g_state.freq_mhz=786;g_state.core_mv=1170;g_state.tuner.phase=TunerPhase::Locked;
 cfg.autotune=true;cfg.tune_goal=1;cfg.power_cap_w=25;
 const uint32_t base=1790002800U/3600*3600;sample(base);assert(rn==1&&stable_n==1);
 for(unsigned i=1;i<=60;i++){sample(base+i*30);}
 assert(stable_n==61&&stable.mhz==786&&blobs.count("stable"));
 sample(base+1866);assert(stable_n==1); // a >65 s gap resets the stability window
 sample(base+3600);assert(blobs.count(std::string("d")+std::to_string((base/86400)%W)));
 auto *stored_day=&week[(base/86400)%W];assert(stored_day->row[(base%86400)/3600].n>0);
 // Per-metric counts prevent one valid hour sample getting the weight of 120.
 Day d;d.day=base/86400;float vals[N];for(auto &x:vals)x=NAN;
 Aggregate a;vals[0]=1000;a.add(d.day*86400,vals);vals[0]=NAN;for(int i=1;i<120;i++)a.add(d.day*86400,vals);d.row[0]=a.finish(3600);
 a=Aggregate{};vals[0]=2000;for(int i=0;i<120;i++)a.add(d.day*86400+3600,vals);d.row[1]=a.finish(3600);
 auto daily=rollup(d);assert(daily.n==240&&decode(daily.x[0],0)==1992);
 // NTP backwards reset discards only partial RAM windows, with no duplicate rows.
 sample(base+120);assert(rn==1&&fn==0&&ah.n==1&&stable_n==1);
 auto old_conf=conf;available=0;assert(set_config()==500&&conf.enabled==old_conf.enabled);
 available=1000;storage_fail=true;assert(set_config()==500&&conf.enabled==old_conf.enabled);
 storage_fail=false;assert(set_config()==0&&conf.enabled&&conf.restore);
 g_state.temp_ok=false;assert(intel::fan_floor()==100);g_state.temp_ok=true;
 deny_lock=true;assert(intel::fan_floor()==100);deny_lock=false;
 uint16_t f=0,mv=0;g_state.vin=4.5;assert(!intel::rollback_point(798,1180,786,25,f,mv));g_state.vin=5.1;
 task_ok=false;assert(set_config()==500&&!intel::rollback_point(798,1180,786,25,f,mv));task_ok=true;
 auto count=blobs.size();available=0;sample(base+7200);assert(!archive_ok&&blobs.size()==count);
 httpd_req_t req{};response.clear();assert(intel::get(&req)==0&&response.find("\"archiveOk\":false")!=std::string::npos);
 std::cout<<"PASS: intelligence archive/stable window, exact missing-metric weights, NTP rollback, NVS reserve/failure, atomic config, sensor/lock fail-safe, unavailable task, JSON API\n";
 free(recent);free(five);free(week);free(save_day);free(save_month);
}
