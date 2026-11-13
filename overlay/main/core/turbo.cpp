#include "turbo.h"
#include "core/state.h"
#include "core/settings.h"
#include "core/intelligence.h"
#include "core/psu.h"
#include "core/json_util.h"
#include "core/hunter.h"
#include "asic/bm13xx.h"
#include "stratum/pools.h"
#include "core/board.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "nvs.h"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <cmath>
#include <cstdlib>
namespace turbo {
namespace {
struct Archive{uint32_t magic=0x54554232;Point points[turbo_math::MapSize];};
Archive archive;uint32_t point_generation[turbo_math::MapSize]={};
SemaphoreHandle_t mu=nullptr;
std::atomic<bool> queued{false},running{false},cancel{false};
std::atomic<unsigned> limit{1000},requested_cap{30},state{0};
std::atomic<Reason> why{Reason::None},fatal_reason{Reason::None};std::atomic<uint32_t> heartbeat{0},clock_change_ms{0};
Point anchor_point;std::atomic<bool> persisted{true};uint32_t generation=0,session=0;int pool=-1;uint16_t original_f=0,original_mv=0;
float baseline_useful=0,window_min_vin=0,last_useful=0;unsigned last_replies=0,over_power=0;int64_t window_started=0;
hunter::WorkSnapshot initial{},first{};
const char*text(Reason r){switch(r){case Reason::Frequency:return "frequency";case Reason::Power:return "power";case Reason::Thermal:return "temperature";case Reason::Supply:return "supply";case Reason::Errors:return "errors";case Reason::Network:return "network";case Reason::Pll:return "pll";case Reason::User:return "user";case Reason::Settings:return "settings";case Reason::Storage:return "storage";case Reason::Telemetry:return "telemetry";case Reason::Samples:return "insufficient_accepted_work";case Reason::Controller:return "controller";case Reason::Voltage:return "voltage";case Reason::Hold:return "fault_hold";default:return "none";}}
struct Guard{bool ok;Guard():ok(mu&&xSemaphoreTake(mu,pdMS_TO_TICKS(100))==pdTRUE){}~Guard(){if(ok)xSemaphoreGive(mu);}};
int active_pool(){int p=-1;for(int i=0;i<4;i++)if(g_state.pools[i].connected&&g_state.pools[i].work_pct==100){if(p>=0)return -1;p=i;}return p;}
bool fresh(){uint32_t now=uint32_t(esp_timer_get_time()/1000),s=g_state.telemetry_ms.load(),h=g_state.hash_counter_ms.load();return s&&now-s<=3000&&((h&&now-h<=10000)||(active()&&clock_change_ms.load()&&now-clock_change_ms.load()<=10000))&&g_state.power_sample_ms.load()&&now-g_state.power_sample_ms.load()<=3000;}
Reason health(){
 if(!board::is_powered()||g_state.status!=SysStatus::Mining)return Reason::Supply;
 if(!g_state.time_synced||time(nullptr)<1577836800 || time(nullptr)>=4102444800LL)return Reason::Telemetry;
 if(!fresh()||!g_state.temp_ok||!g_state.vr_temp_ok||!std::isfinite(g_state.pin)||g_state.pin<=0||!std::isfinite(g_state.iin)||g_state.iin<=0||!std::isfinite(g_state.iout)||g_state.iout<=0||!std::isfinite(g_state.vin)||!std::isfinite(g_state.vout)||g_state.vout<.8f||g_state.vout>1.32f||g_state.core_mv>1300)return Reason::Telemetry;
 if(g_state.chip_temp_max>=65||g_state.vr_temp>=75||!g_state.fan_present[0]||g_state.fan_rpm[0]<600)return Reason::Thermal;
 auto level=psu::state().level;
 if(g_state.vin<4.85f||g_state.vin>5.35f||g_state.iin>5.5f||g_state.iout>24.f||level==psu::Level::Weak||level==psu::Level::Bad)return Reason::Supply;
 if(!std::isfinite(g_state.error_pct)||g_state.error_pct<0||g_state.error_pct>=(active()?4:1))return Reason::Errors;
 if(!g_state.pool_connected||active_pool()<0)return Reason::Network;
 auto&cfg=settings::get();if(!cfg.autotune||cfg.tune_goal!=1||cfg.chip_tune||cfg.pool_mode!=PoolMode::Failover)return Reason::Settings;
 for(auto off:cfg.chip_off)if(off)return Reason::Settings;
 return Reason::None;
}
bool save(){
 nvs_stats_t st{};if(nvs_get_stats(nullptr,&st)!=ESP_OK||st.free_entries<128+(sizeof(archive)+31)/32+4)return false;
 nvs_handle_t h;if(nvs_open("af_turbo",NVS_READWRITE,&h)!=ESP_OK)return false;
 bool good=nvs_set_blob(h,"map",&archive,sizeof(archive))==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);return good;
}
}
void start(){mu=xSemaphoreCreateMutex();if(!mu)return;nvs_handle_t h;if(nvs_open("af_turbo",NVS_READONLY,&h)==ESP_OK){Archive loaded;size_t n=sizeof(loaded);if(nvs_get_blob(h,"map",&loaded,&n)==ESP_OK&&n==sizeof(loaded)&&loaded.magic==archive.magic){archive=loaded;for(auto&p:archive.points)if(!turbo_math::valid(p))p=Point{};}nvs_close(h);}/* no active flag/settings restored */}
bool pending(){return queued.load();}bool active(){return running.load();}bool engaged(){unsigned s=state.load();return pending()||active()||s==1||s==2||s==3||s==5;}bool cancelled(){return cancel.load()||fatal_reason.load()!=Reason::None;}
uint16_t max_frequency(){return active()?uint16_t(limit.load()):800;}
float power_budget(){return turbo_math::budget(float(requested_cap.load()),false,g_state.vin,g_state.chip_temp_max,g_state.vr_temp,psu::state().level==psu::Level::Ok);}
void stop(Reason r){if(r!=Reason::Errors&&r!=Reason::Power)fatal_reason=r;why=r;cancel=true;if(engaged())state=5;}
Reason reason(){auto r=fatal_reason.load();return r==Reason::None?why.load():r;}
void disarm(Reason r){fatal_reason=r;stop(r);running=false;queued=false;state=5;}
Reason monitor_trip(){if(!active())return Reason::None;uint32_t now=uint32_t(esp_timer_get_time()/1000);if(now-heartbeat.load()>10000)return Reason::Controller;if(std::isfinite(g_state.pin)&&g_state.pin>float(requested_cap.load()))return Reason::Power;if(std::isfinite(g_state.iin)&&g_state.iin>5.7f)return Reason::Supply;return Reason::None;}
bool begin(Point&a){
 if(!queued.exchange(false))return false;
 if(cancelled()){state=4;return false;}
 Reason r=health();if(r!=Reason::None){stop(r);state=4;return false;}
 uint16_t f,mv;float gh;if(g_state.tuner.phase!=TunerPhase::Locked||!intel::stable_point(f,mv,gh)||f>800||mv>1300||g_state.pin>power_budget()*.95f){stop(Reason::Power);state=4;return false;}
 a=anchor_point={f,mv,g_state.pin,gh,0,uint32_t(time(nullptr)),uint16_t(requested_cap.load()),0,g_state.chip_temp_max,g_state.vr_temp,g_state.vin};pool=active_pool();session=pools::session_id(pool);original_f=settings::get().freq_mhz;original_mv=settings::get().core_mv;initial=hunter::work_snapshot(pool);++generation;baseline_useful=0;clock_change_ms=0;window_min_vin=g_state.vin;over_power=0;why=Reason::None;heartbeat=uint32_t(esp_timer_get_time()/1000);state=2;running=true;return true;
}
bool check(){
 heartbeat=uint32_t(esp_timer_get_time()/1000);if(cancelled())return false;
 auto r=health();if(r!=Reason::None){stop(r);return false;}
 if(pool!=active_pool()||session!=pools::session_id(pool)){stop(Reason::Network);return false;}
 auto&cfg=settings::get();if(cfg.freq_mhz!=original_f||cfg.core_mv!=original_mv){stop(Reason::Settings);return false;}
 auto w=hunter::work_snapshot(pool);if(w.failed!=initial.failed||w.missing!=initial.missing){stop(Reason::Network);return false;}
 window_min_vin=std::min(window_min_vin,g_state.vin);
 if(g_state.pin>power_budget()){if(++over_power>=2){stop(Reason::Power);return false;}}else over_power=0;
 return true;
}
void changing(){clock_change_ms=uint32_t(esp_timer_get_time()/1000);}
void window_begin(){window_min_vin=g_state.vin;first=hunter::work_snapshot(pool);window_started=esp_timer_get_time();}
bool window_end(float ghs){
 auto w=hunter::work_snapshot(pool);double sec=(esp_timer_get_time()-window_started)/1e6;uint32_t accepted=w.accepted-first.accepted,rejected=w.rejected-first.rejected;
 double work=w.work-first.work,square=w.squared-first.squared;double effective=square>0?work*work/square:0;
 if(sec<=0||accepted<30||effective<30||work<=0||!std::isfinite(work)){stop(Reason::Samples);return false;}
 if(rejected>1&&double(rejected)/(accepted+rejected)>.01){stop(Reason::Network);return false;}
 last_useful=float(work*4294967296./sec/1e9);last_replies=accepted;
 double base=baseline_useful;
 if(!std::isfinite(last_useful)||last_useful<base*.5||ghs<g_state.expected_ghs*.92f){stop(Reason::Errors);return false;}
 if(baseline_useful==0)baseline_useful=last_useful;
 return true;
}
bool remember(uint16_t f,uint16_t mv,float ghs,float watts,float chip,float vr){
 Point p{f,mv,watts,ghs,last_useful,uint32_t(time(nullptr)),uint16_t(requested_cap.load()),uint16_t(last_replies>65535?65535:last_replies),chip>=0?chip:g_state.chip_temp_max,vr>=0?vr:g_state.vr_temp,window_min_vin};if(!turbo_math::valid(p)){stop(Reason::Telemetry);return false;}
 {Guard g;if(!g.ok)return false;unsigned slot=0;for(unsigned i=0;i<turbo_math::MapSize;i++){if(archive.points[i].mhz==f&&archive.points[i].mv==mv&&archive.points[i].cap==p.cap){slot=i;break;}if(!archive.points[i].mhz){slot=i;break;}if(archive.points[i].time<archive.points[slot].time)slot=i;}archive.points[slot]=p;point_generation[slot]=generation;}
 persisted=save();if(!persisted){stop(Reason::Storage);return false;}return true;
}
Point fallback(uint16_t failed,float cap){Point p=anchor_point;Guard g;if(!g.ok)return p;for(unsigned i=0;i<turbo_math::MapSize;i++){auto&v=archive.points[i];if(point_generation[i]==generation&&v.mhz<failed&&v.mhz>p.mhz&&v.watts<=cap*.95f&&v.mv<=g_state.core_mv)p=v;}return p;}
void holding(Reason r){if(fatal_reason.load()!=Reason::None)return;why=r;state=3;cancel=false;over_power=0;}
void finish(){running=false;queued=false;cancel=false;state=4;}
esp_err_t get(httpd_req_t*req){
 Archive copy;{Guard g;if(!g.ok)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"turbo unavailable");copy=archive;}
 char*b=static_cast<char*>(malloc(8192));if(!b)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"no memory");
 int n=snprintf(b,8192,"{\"available\":true,\"armed\":%s,\"state\":%u,\"maxFreq\":%u,\"requestedPower\":%u,\"effectivePower\":%.2f,\"voltageLimit\":1300,\"reason\":\"%s\",\"powerEstimated\":true,\"persisted\":%s,\"points\":[",engaged()?"true":"false",state.load(),limit.load(),requested_cap.load(),double(power_budget()),text(reason()),persisted.load()?"true":"false");
 bool comma=false;for(auto&p:copy.points)if(turbo_math::valid(p)&&n>0&&n<7800){n+=snprintf(b+n,8192-size_t(n),"%s{\"frequency\":%u,\"millivolts\":%u,\"watts\":%.3f,\"asicGHs\":%.3f,\"acceptedGHs\":%.3f,\"time\":%lu,\"powerCap\":%u,\"accepted\":%u,\"maxAsicC\":%.2f,\"maxVrmC\":%.2f,\"minVin\":%.3f}",comma?",":"",unsigned(p.mhz),unsigned(p.mv),double(p.watts),double(p.ghs),double(p.useful_ghs),(unsigned long)p.time,unsigned(p.cap),unsigned(p.replies),double(p.max_asic),double(p.max_vr),double(p.min_vin));comma=true;}
 esp_err_t out;if(n<=0||n>=8189)out=httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"response overflow");else {snprintf(b+n,8192-size_t(n),"]}");httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");out=httpd_resp_sendstr(req,b);}free(b);return out;
}
esp_err_t set(httpd_req_t*req){
 char body[192];if(req->content_len<=0||size_t(req->content_len)>=sizeof(body))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"bad body");int n=0;while(n<req->content_len){int k=httpd_req_recv(req,body+n,req->content_len-n);if(k<=0)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"incomplete body");n+=k;}body[n]=0;
 cJSON*j=json_parse(body);auto*en=j?cJSON_GetObjectItem(j,"enabled"):nullptr;auto*confirm=j?cJSON_GetObjectItem(j,"confirm"):nullptr;auto*freq=j?cJSON_GetObjectItem(j,"maxFreq"):nullptr;auto*cap=j?cJSON_GetObjectItem(j,"powerLimit"):nullptr;
 bool valid=cJSON_IsBool(en),enabled=cJSON_IsTrue(en);bool params=cJSON_IsString(confirm)&&!strcmp(confirm->valuestring,"TURBO1000")&&cJSON_IsNumber(freq)&&cJSON_IsNumber(cap)&&std::isfinite(freq->valuedouble)&&std::isfinite(cap->valuedouble)&&freq->valuedouble==std::floor(freq->valuedouble)&&cap->valuedouble==std::floor(cap->valuedouble)&&freq->valuedouble>=800&&freq->valuedouble<=1000&&cap->valuedouble>=18&&cap->valuedouble<=30;
 unsigned f=params?unsigned(freq->valuedouble):0,p=params?unsigned(cap->valuedouble):0;cJSON_Delete(j);
 if(!valid|| (enabled&&(!params||!turbo_math::max_valid(f,p))))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Confirm TURBO1000; maxFreq800..1000 step25; power18..30W");
 if(!enabled){stop(Reason::User);return httpd_resp_sendstr(req,"Stopping in stock tuner");}
 Guard guard;if(!guard.ok)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"turbo unavailable");
 uint16_t sf,sv;float gh,actual;auto observed=hunter::work_snapshot(active_pool());
 if(engaged()||observed.accepted<100||observed.seconds<1800||g_state.tuner.phase!=TunerPhase::Locked||hunter::benchmark_running()||health()!=Reason::None||!intel::stable_point(sf,sv,gh)||sf>800||!asic::pll_supported(float(f),actual))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Need30min measured stable Gamma point, fresh power/sensors, V1 failover and no running experiment");
 requested_cap=p;limit=f;
 if(g_state.pin>power_budget()*.95f)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Stable point exceeds derated PSU budget");
 fatal_reason=Reason::None;why=Reason::None;cancel=false;state=1;queued=true;return httpd_resp_sendstr(req,"Queued in stock tuner; no forced1000MHz");
}
}
