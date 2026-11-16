#include <cassert>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <iostream>
#include "../overlay/main/core/turbo.cpp"
#include "asic/bm1370_pll.h"
MinerState g_state{};static Settings cfg{};namespace settings{Settings&get(){return cfg;}void save(){}}
static int64_t now_us=1000000;int64_t esp_timer_get_time(){return now_us;}
static bool powered=true,stable=true,bench=false,write_fail=false;static uint32_t session_id=10;static unsigned nvs_writes=0;static size_t free_nvs=1000;
static hunter::WorkSnapshot work{};static std::map<std::string,std::vector<unsigned char>>saved;static bool locked=false;static std::string body,response;static size_t pos=0;
namespace board{bool is_powered(){return powered;}}
namespace pools{uint32_t session_id(int){return ::session_id;}}
namespace hunter{bool benchmark_running(){return bench;}WorkSnapshot work_snapshot(int){return work;}}
namespace intel{bool stable_point(uint16_t&f,uint16_t&mv,float&ghs){f=786;mv=1170;ghs=1550;return stable;}}
namespace asic{float frequency(){return float(g_state.freq_mhz);}bool pll_supported(float target,float&actual){auto p=bm1370_pll::solve(target);actual=p.actual;return bool(p);}}
namespace psu{static State v{};const State&state(){return v;}}
SemaphoreHandle_t xSemaphoreCreateMutex(){return reinterpret_cast<void*>(1);}int xSemaphoreTake(SemaphoreHandle_t,unsigned){if(locked)return 0;locked=true;return pdTRUE;}int xSemaphoreGive(SemaphoreHandle_t){assert(locked);locked=false;return pdTRUE;}
int nvs_open(const char*ns,int,nvs_handle_t*h){assert(!strcmp(ns,"af_turbo"));*h=1;return ESP_OK;}int nvs_get_blob(nvs_handle_t,const char*k,void*p,size_t*n){auto&v=saved[k];if(*n!=v.size())return ESP_FAIL;memcpy(p,v.data(),*n);return ESP_OK;}int nvs_set_blob(nvs_handle_t,const char*k,const void*p,size_t n){nvs_writes++;if(write_fail)return ESP_FAIL;auto*a=(const unsigned char*)p;saved[k]={a,a+n};return ESP_OK;}int nvs_commit(nvs_handle_t){return write_fail?ESP_FAIL:ESP_OK;}void nvs_close(nvs_handle_t){}int nvs_get_stats(const char*,nvs_stats_t*s){s->free_entries=free_nvs;return ESP_OK;}
int httpd_req_recv(httpd_req_t*,char*p,size_t n){n=std::min(n,body.size()-pos);memcpy(p,body.data()+pos,n);pos+=n;return int(n);}int httpd_resp_send_err(httpd_req_t*,int s,const char*t){response=t;return s;}int httpd_resp_sendstr(httpd_req_t*,const char*t){response=t;return 0;}int httpd_resp_set_type(httpd_req_t*,const char*){return 0;}int httpd_resp_set_hdr(httpd_req_t*,const char*,const char*){return 0;}
static int command(std::string s){body=s;pos=0;httpd_req_t r{int(body.size())};return turbo::set(&r);}
static void fresh(){auto t=uint32_t(now_us/1000);g_state.telemetry_ms=t;g_state.hash_counter_ms=t;g_state.power_sample_ms=t;}
static void reset(){turbo::finish();powered=stable=true;bench=write_fail=false;free_nvs=1000;session_id=10;turbo::psu_watts=30;turbo::psu_amps=6;turbo::requested_cap=30;cfg.overclock=true;cfg.autotune=true;cfg.tune_goal=1;cfg.pool_mode=PoolMode::Failover;cfg.freq_mhz=786;cfg.core_mv=1170;cfg.power_cap_w=25;cfg.chip_tune=false;g_state.status=SysStatus::Mining;g_state.time_synced=true;g_state.tuner.phase=TunerPhase::Locked;g_state.pool_connected=g_state.temp_ok=g_state.vr_temp_ok=g_state.fan_present[0]=true;g_state.fan_rpm[0]=1500;g_state.chip_temp_max=55;g_state.vr_temp=60;g_state.vin=5.1;g_state.vout=1.17;g_state.pin=23;g_state.iin=23/5.1;g_state.iout=15;g_state.error_pct=.1;g_state.freq_mhz=786;g_state.core_mv=1170;g_state.expected_ghs=1600;g_state.pools[0].connected=true;g_state.pools[0].work_pct=100;psu::v.level=psu::Level::Ok;work={1000000,1024000000,3600,1000,0,0,0};fresh();}
static const char*arm="{\"enabled\":true,\"confirm\":\"TURBO1000\",\"maxFreq\":1000,\"powerLimit\":30}";
static void begin(){assert(command(arm)==0&&turbo::pending()&&!turbo::active());turbo::Point anchor;assert(turbo::begin(anchor));assert(anchor.mhz==786&&anchor.mv==1170&&g_state.freq_mhz==786&&cfg.power_cap_w==25);}
int main(){
 turbo::start();assert(!turbo::unlocked()&&turbo::max_frequency()==800);reset();assert(!turbo::engaged()&&turbo::max_frequency()==1000);
 assert(command("{\"enabled\":true}")==400);assert(command("{\"enabled\":true,\"confirm\":\"TURBO1000\",\"maxFreq\":1025,\"powerLimit\":30}")==400);
 stable=false;assert(command(arm)==400);reset();bench=true;assert(command(arm)==400);reset();g_state.power_sample_ms=0;assert(command(arm)==400);reset();
 begin();assert(turbo::max_frequency()==1000&&turbo::power_budget()==25.5f);assert(turbo::check());
 turbo::window_begin();now_us+=300000000;fresh();work.accepted+=100;work.work+=102400;work.squared+=104857600;assert(turbo::window_end(1600));assert(turbo::remember(800,1170,1600,23.5));assert(nvs_writes==1);assert(turbo::fallback(825,25).mhz==800);
 g_state.vin=4.9;assert(turbo::power_budget()>22&&turbo::power_budget()<24);g_state.pin=24;assert(turbo::check());assert(!turbo::check()&&turbo::reason()==turbo::Reason::Power);reset();begin();g_state.vin=4.7;assert(!turbo::check()&&turbo::reason()==turbo::Reason::Supply);
 reset();begin();session_id++;assert(!turbo::check()&&turbo::reason()==turbo::Reason::Network);
 reset();begin();work.failed++;assert(!turbo::check()&&turbo::reason()==turbo::Reason::Network);
 reset();begin();turbo::changing();g_state.hash_counter_ms=0;assert(turbo::check());now_us+=11000000;g_state.telemetry_ms=uint32_t(now_us/1000);g_state.power_sample_ms=uint32_t(now_us/1000);assert(!turbo::check()&&turbo::reason()==turbo::Reason::Telemetry);
 reset();begin();g_state.chip_temp_max=66;assert(!turbo::check()&&turbo::reason()==turbo::Reason::Thermal);
 reset();begin();now_us+=11000000;assert(turbo::monitor_trip()==turbo::Reason::Controller);fresh();turbo::check();g_state.pin=30.1;assert(turbo::monitor_trip()==turbo::Reason::Power);
 reset();begin();turbo::window_begin();now_us+=300000000;fresh();work.accepted+=2;work.work+=2048;work.squared+=2097152;assert(!turbo::window_end(1600)&&turbo::reason()==turbo::Reason::Samples);
 reset();begin();free_nvs=128;assert(!turbo::remember(825,1170,1650,24)&&turbo::reason()==turbo::Reason::Storage);
 reset();begin();assert(command("{\"enabled\":false}")==0&&turbo::cancelled());turbo::holding(turbo::Reason::Frequency);assert(turbo::cancelled()&&turbo::reason()==turbo::Reason::User);turbo::finish();assert(!turbo::active());
 reset();turbo::psu_watts=15;assert(turbo::monitor_trip()==turbo::Reason::Power);cfg.freq_mhz=900;cfg.core_mv=1250;turbo::disarm(turbo::Reason::Supply);assert(cfg.freq_mhz==525&&cfg.core_mv==1150&&!turbo::engaged());
 reset();assert(turbo_math::budget(30,40,8,5.1,55,60,true).effective==30);assert(turbo_math::budget(30,120,24,5.1,55,60,true).effective==30);assert(turbo_math::budget(30,40,8,4.9,55,60,true).effective==27);
 unsigned writes=nvs_writes;turbo::start();assert(!turbo::engaged()&&nvs_writes==writes);httpd_req_t req{};assert(turbo::get(&req)==0);auto*j=cJSON_Parse(response.c_str());assert(j);cJSON_Delete(j);auto seed=turbo::archive.points[0];for(unsigned i=0;i<16;i++){turbo::archive.points[i]=seed;turbo::archive.points[i].mhz=uint16_t(600+i*25);}assert(turbo::get(&req)==0);j=cJSON_Parse(response.c_str());assert(cJSON_GetArraySize(cJSON_GetObjectItem(j,"points"))==16);cJSON_Delete(j);
 reset();turbo::best_score=0;g_state.freq_mhz=825;turbo::last_score=1650;assert(turbo::better(1650,1170));g_state.freq_mhz=900;turbo::last_score=1600;assert(!turbo::better(1600,1170)&&turbo::best_f==825);
 reset();cfg.overclock=false;assert(command(arm)==400);cfg.overclock=true;
 assert(command("{\"action\":\"configure\",\"psuWatts\":40,\"psuAmps\":8,\"maxFreq\":1000,\"powerLimit\":30}")==0);assert(turbo::power_budget()==30);
 turbo::start();assert(turbo::unlocked()&&!turbo::engaged()&&turbo::power_budget()==30); // permission and PSU survive, no auto experiment
 cfg.freq_mhz=900;cfg.tuned_freq=900;turbo::safe_boot();assert(cfg.freq_mhz<=800&&cfg.tuned_freq==0&&cfg.overclock);
 write_fail=true;assert(command("{\"action\":\"configure\",\"psuWatts\":60,\"psuAmps\":12,\"maxFreq\":1000,\"powerLimit\":30}")==500);assert(turbo::psu_watts==40);write_fail=false;
 assert(command("{\"action\":\"configure\",\"psuWatts\":-1,\"psuAmps\":8,\"maxFreq\":1000,\"powerLimit\":30}")==400);
 saved["config"][0]^=1;turbo::start();assert(!cfg.overclock&&!turbo::engaged()); // corrupt config fails closed
 assert(turbo::get(&req)==0);j=cJSON_Parse(response.c_str());assert(j);cJSON_Delete(j);
 if(getenv("AXEFORGE_API_JSON"))std::cout<<"API_JSON "<<response<<'\n';
 std::cout<<"PASS manual-only Turbo/API, no forced clock/settings write,PSU-derived30W budget/reserve/derating and persistent unlock, sensor/session/accepted-work guards,16-point NVS map/failure, watchdog/stop and no armed persistence\n";
}
