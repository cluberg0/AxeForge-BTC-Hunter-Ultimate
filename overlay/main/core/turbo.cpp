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
#include "core/board_config.h"
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
struct Config{uint32_t magic=0x554e4c31;float watts=30,amps=6;uint16_t maximum=1000,cap=30;};
Config config;
struct Trial{uint16_t f=0,mv=0;float gh=0,w=0;unsigned verdict=0;};Trial trials[16];unsigned trial_count=0;
std::atomic<float> psu_watts{30},psu_amps{6},best_score{0};
std::atomic<unsigned> best_f{0},best_mv{0};std::atomic<float> best_watts{0};
SemaphoreHandle_t mu=nullptr;
std::atomic<bool> queued{false},running{false},cancel{false};
std::atomic<unsigned> limit{1000},requested_cap{30},state{0};
std::atomic<Reason> why{Reason::None},fatal_reason{Reason::None};std::atomic<uint32_t> heartbeat{0},clock_change_ms{0};
Point anchor_point;std::atomic<bool> persisted{true};uint32_t generation=0,session=0;int pool=-1;uint16_t original_f=0,original_mv=0;
float last_score=0;float baseline_useful=0,window_min_vin=0,last_useful=0;unsigned last_replies=0,over_power=0;int64_t window_started=0;
hunter::WorkSnapshot initial{},first{};
const char*text(Reason r){switch(r){case Reason::Frequency:return "frequency";case Reason::Power:return "power";case Reason::Thermal:return "temperature";case Reason::Supply:return "supply";case Reason::Errors:return "errors";case Reason::Network:return "network";case Reason::Pll:return "pll";case Reason::User:return "user";case Reason::Settings:return "settings";case Reason::Storage:return "storage";case Reason::Telemetry:return "telemetry";case Reason::Samples:return "insufficient_accepted_work";case Reason::Controller:return "controller";case Reason::Voltage:return "voltage";case Reason::Hold:return "fault_hold";default:return "none";}}
struct Guard{bool ok;Guard():ok(mu&&xSemaphoreTake(mu,pdMS_TO_TICKS(100))==pdTRUE){}~Guard(){if(ok)xSemaphoreGive(mu);}};
int active_pool(){int p=-1;for(int i=0;i<4;i++)if(g_state.pools[i].connected&&g_state.pools[i].work_pct==100){if(p>=0)return -1;p=i;}return p;}
bool fresh(){uint32_t now=uint32_t(esp_timer_get_time()/1000),s=g_state.telemetry_ms.load(),h=g_state.hash_counter_ms.load();return s&&now-s<=3000&&((h&&now-h<=10000)||(unlocked()&&clock_change_ms.load()&&now-clock_change_ms.load()<=10000))&&g_state.power_sample_ms.load()&&now-g_state.power_sample_ms.load()<=3000;}
Reason health(bool search=true){
 if(!board::is_powered()||g_state.status!=SysStatus::Mining)return Reason::Supply;
 if(!g_state.time_synced||time(nullptr)<1577836800 || time(nullptr)>=4102444800LL)return Reason::Telemetry;
 if(!fresh()||!g_state.temp_ok||!g_state.vr_temp_ok||!std::isfinite(g_state.pin)||g_state.pin<=0||!std::isfinite(g_state.iin)||g_state.iin<=0||!std::isfinite(g_state.iout)||g_state.iout<=0||!std::isfinite(g_state.vin)||!std::isfinite(g_state.vout)||g_state.vout<.8f||g_state.vout>1.32f||g_state.core_mv>1300)return Reason::Telemetry;
 if(g_state.chip_temp_max>=65||g_state.vr_temp>=75||!g_state.fan_present[0]||g_state.fan_rpm[0]<600)return Reason::Thermal;
 auto level=psu::state().level;
 if(g_state.vin<4.85f||g_state.vin>5.35f||g_state.iin>turbo_math::budget(30,psu_watts.load(),psu_amps.load(),g_state.vin,0,0,true).current_limit||g_state.iout>24.f||level==psu::Level::Weak||level==psu::Level::Bad)return Reason::Supply;
 if(!std::isfinite(g_state.error_pct)||g_state.error_pct<0||g_state.error_pct>=(active()?4:1))return Reason::Errors;
 if(!g_state.pool_connected||active_pool()<0)return Reason::Network;
 auto&cfg=settings::get();if(search&&(!cfg.autotune||cfg.tune_goal!=1||cfg.chip_tune||cfg.pool_mode!=PoolMode::Failover))return Reason::Settings;
 for(auto off:cfg.chip_off)if(search&&off)return Reason::Settings;
 return Reason::None;
}
bool save(){
 nvs_stats_t st{};if(nvs_get_stats(nullptr,&st)!=ESP_OK||st.free_entries<128+(sizeof(archive)+31)/32+4)return false;
 nvs_handle_t h;if(nvs_open("af_turbo",NVS_READWRITE,&h)!=ESP_OK)return false;
 bool good=nvs_set_blob(h,"map",&archive,sizeof(archive))==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);return good;
}
}
void sync_cap(uint16_t cap){requested_cap=cap&&cap<=30?cap:30;}
bool supported(){
#if defined(AF_ASIC_BM1370) && AF_NUM_ASICS == 1 && defined(AF_EXPERIMENT_FREQ_MHZ)
 return AF_EXPERIMENT_FREQ_MHZ==1000;
#else
 return false;
#endif
}
bool unlocked(){return supported()&&settings::get().overclock;}
void safe_boot(){auto&c=settings::get();if(!supported())c.overclock=false;if(c.freq_mhz>800||c.tuned_freq>800){c.freq_mhz=525;c.core_mv=1150;c.tuned_freq=0;c.tuned_mv=0;}/* leave unlock, PSU and user cap intact; no NVS erase */}
void start(){mu=xSemaphoreCreateMutex();if(!mu)return;nvs_handle_t h;if(nvs_open("af_turbo",NVS_READONLY,&h)==ESP_OK){Archive loaded;size_t n=sizeof(loaded);if(nvs_get_blob(h,"map",&loaded,&n)==ESP_OK&&n==sizeof(loaded)&&loaded.magic==archive.magic){archive=loaded;for(auto&p:archive.points)if(!turbo_math::valid(p))p=Point{};}
 Config c;n=sizeof(c);auto e=nvs_get_blob(h,"config",&c,&n);if(e==ESP_OK){if(n==sizeof(c)&&c.magic==config.magic&&turbo_math::psu_valid(c.watts,c.amps)&&turbo_math::max_valid(c.maximum,c.cap))config=c;else {settings::get().overclock=false;persisted=false;why=Reason::Storage;}}nvs_close(h);}
 psu_watts=config.watts;psu_amps=config.amps;limit=config.maximum;requested_cap=config.cap;sync_cap(settings::get().power_cap_w);safe_boot();}
bool manual_check(float proposed_cap){auto r=health(false);if(r!=Reason::None){why=r;return false;}float cap=proposed_cap<0?float(settings::get().power_cap_w):proposed_cap;if(cap==0)cap=30;auto budget=turbo_math::budget(cap,psu_watts.load(),psu_amps.load(),g_state.vin,g_state.chip_temp_max,g_state.vr_temp,psu::state().level==psu::Level::Ok);if(!std::isfinite(cap)||cap>30||g_state.pin>budget.effective){why=Reason::Power;return false;}return true;}

bool pending(){return queued.load();}bool active(){return running.load();}bool engaged(){unsigned s=state.load();return pending()||active()||s==1||s==2||s==3||s==5;}bool cancelled(){return cancel.load()||fatal_reason.load()!=Reason::None;}
uint16_t max_frequency(){return unlocked()?uint16_t(limit.load()):800;}
float power_budget(){return turbo_math::budget(unlocked()?float(requested_cap.load()):25.f,psu_watts.load(),psu_amps.load(),g_state.vin,g_state.chip_temp_max,g_state.vr_temp,psu::state().level==psu::Level::Ok).effective;}
void stop(Reason r){if(r!=Reason::Errors&&r!=Reason::Power)fatal_reason=r;why=r;cancel=true;if(engaged())state=5;}
Reason reason(){auto r=fatal_reason.load();return r==Reason::None?why.load():r;}
void disarm(Reason r){bool owner=engaged();fatal_reason=r;stop(r);running=false;queued=false;state=owner?5:4;auto&c=settings::get();c.freq_mhz=525;c.core_mv=1150;c.tuned_freq=c.tuned_mv=0;}
Reason monitor_trip(){if(!active()&&!unlocked())return Reason::None;uint32_t now=uint32_t(esp_timer_get_time()/1000);if(active()&&now-heartbeat.load()>10000)return Reason::Controller;if(std::isfinite(g_state.pin)&&g_state.pin>std::min(float(requested_cap.load()),std::min(psu_watts.load(),5.f*psu_amps.load())))return Reason::Power;if(std::isfinite(g_state.iin)&&g_state.iin>std::min(psu_amps.load(),6.8f))return Reason::Supply;return Reason::None;}
bool begin(Point&a){
 if(!unlocked()||!queued.exchange(false))return false;
 if(cancelled()){state=4;return false;}
 Reason r=health();if(r!=Reason::None){stop(r);state=4;return false;}
 uint16_t f,mv;float gh;if(g_state.tuner.phase!=TunerPhase::Locked||!intel::stable_point(f,mv,gh)||f>800||mv>1300||g_state.pin>power_budget()*.95f){stop(Reason::Power);state=4;return false;}
 a=anchor_point={f,mv,g_state.pin,gh,0,uint32_t(time(nullptr)),uint16_t(requested_cap.load()),0,g_state.chip_temp_max,g_state.vr_temp,g_state.vin};pool=active_pool();session=pools::session_id(pool);original_f=settings::get().freq_mhz;original_mv=settings::get().core_mv;initial=hunter::work_snapshot(pool);++generation;best_score=0;best_f=0;best_mv=0;best_watts=0;trial_count=0;baseline_useful=0;clock_change_ms=0;window_min_vin=g_state.vin;over_power=0;why=Reason::None;heartbeat=uint32_t(esp_timer_get_time()/1000);state=2;running=true;return true;
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
 last_useful=float(work*4294967296./sec/1e9);last_replies=accepted;last_score=ghs*float(double(accepted)/(double(accepted)+rejected));
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
Point fallback(uint16_t failed,float cap){Point p=anchor_point;Guard g;if(!g.ok)return p;for(unsigned i=0;i<turbo_math::MapSize;i++){auto&v=archive.points[i];if(point_generation[i]==generation&&v.mhz<failed&&v.ghs>p.ghs&&v.watts<=cap*.95f&&v.mv<=g_state.core_mv)p=v;}return p;}
bool better(float ghs,uint16_t mv){float score=std::min(ghs,last_score);if(score>best_score.load()*1.01f || (score>=best_score.load()*.99f&&mv<best_mv.load())){best_score=score;best_f=g_state.freq_mhz;best_mv=mv;best_watts=g_state.pin;return true;}return false;}
void trial(uint16_t f,uint16_t mv,float gh,float w,unsigned verdict){Guard g;if(!g.ok)return;trials[trial_count++%16]={f,mv,std::isfinite(gh)?gh:0,std::isfinite(w)?w:0,verdict};}
void holding(Reason r){if(fatal_reason.load()!=Reason::None)return;why=r;state=3;cancel=false;over_power=0;}
void finish(){running=false;queued=false;cancel=false;state=4;}
esp_err_t get(httpd_req_t*req){
 Archive copy;{Guard g;if(!g.ok)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"turbo unavailable");copy=archive;}
 char*b=static_cast<char*>(malloc(12288));if(!b)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"no memory");
 int n=snprintf(b,12288,"{\"available\":true,\"armed\":%s,\"state\":%u,\"maxFreq\":%u,\"requestedPower\":%u,\"effectivePower\":%.2f,\"voltageLimit\":1300,\"reason\":\"%s\",\"powerEstimated\":true,\"persisted\":%s",engaged()?"true":"false",state.load(),limit.load(),requested_cap.load(),double(power_budget()),text(reason()),persisted.load()?"true":"false");
 float applied=0;asic::pll_supported(asic::frequency(),applied);
 auto budget=turbo_math::budget(unlocked()?float(requested_cap.load()):25.f,psu_watts.load(),psu_amps.load(),g_state.vin,g_state.chip_temp_max,g_state.vr_temp,psu::state().level==psu::Level::Ok);
 n+=snprintf(b+n,12288-size_t(n),",\"unlocked\":%s,\"activeMaxFreq\":%u,\"userMaxPower\":%u,\"psuWatts\":%.1f,\"psuAmps\":%.1f,\"powerReserve\":%.2f,\"inputMargin\":%.2f,\"budgetReason\":\"%s\",\"appliedFreq\":%.3f,\"bestFreq\":%u,\"bestMv\":%u,\"bestGHs\":%.3f,\"bestWatts\":%.3f,\"trials\":[",unlocked()?"true":"false",unlocked()&&psu::state().level!=psu::Level::Weak&&psu::state().level!=psu::Level::Bad?1000u:800u,unlocked()?30u:25u,double(psu_watts.load()),double(psu_amps.load()),double(budget.reserve),double(budget.margin),budget.reason,double(applied),best_f.load(),best_mv.load(),double(best_score.load()),double(best_watts.load()));
 {Guard g;if(!g.ok){free(b);return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"busy");}unsigned count=std::min(trial_count,16u);for(unsigned i=0;i<count;i++){auto&t=trials[(trial_count-count+i)%16];n+=snprintf(b+n,12288-size_t(n),"%s[%u,%u,%.3f,%.3f,%u]",i?",":"",unsigned(t.f),unsigned(t.mv),double(t.gh),double(t.w),t.verdict);}}
 n+=snprintf(b+n,12288-size_t(n),"],\"points\":[");
 bool comma=false;for(auto&p:copy.points)if(turbo_math::valid(p)&&n>0&&n<11500){n+=snprintf(b+n,12288-size_t(n),"%s{\"frequency\":%u,\"millivolts\":%u,\"watts\":%.3f,\"asicGHs\":%.3f,\"acceptedGHs\":%.3f,\"time\":%lu,\"powerCap\":%u,\"accepted\":%u,\"maxAsicC\":%.2f,\"maxVrmC\":%.2f,\"minVin\":%.3f}",comma?",":"",unsigned(p.mhz),unsigned(p.mv),double(p.watts),double(p.ghs),double(p.useful_ghs),(unsigned long)p.time,unsigned(p.cap),unsigned(p.replies),double(p.max_asic),double(p.max_vr),double(p.min_vin));comma=true;}
 esp_err_t out;if(n<=0||n>=12285)out=httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"response overflow");else {snprintf(b+n,12288-size_t(n),"]}");httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");out=httpd_resp_sendstr(req,b);}free(b);return out;
}
esp_err_t set(httpd_req_t*req){
 char body[192];if(req->content_len<=0||size_t(req->content_len)>=sizeof(body))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"bad body");int n=0;while(n<req->content_len){int k=httpd_req_recv(req,body+n,req->content_len-n);if(k<=0)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"incomplete body");n+=k;}body[n]=0;
 cJSON*j=json_parse(body);auto*en=j?cJSON_GetObjectItem(j,"enabled"):nullptr;auto*confirm=j?cJSON_GetObjectItem(j,"confirm"):nullptr;auto*freq=j?cJSON_GetObjectItem(j,"maxFreq"):nullptr;auto*cap=j?cJSON_GetObjectItem(j,"powerLimit"):nullptr;
 auto*action=j?cJSON_GetObjectItem(j,"action"):nullptr;
 if(cJSON_IsString(action)&&!strcmp(action->valuestring,"configure")){
  auto*w=cJSON_GetObjectItem(j,"psuWatts"),*a=cJSON_GetObjectItem(j,"psuAmps");
  bool ok=unlocked()&&!engaged()&&cJSON_IsNumber(w)&&cJSON_IsNumber(a)&&turbo_math::psu_valid(w->valuedouble,a->valuedouble)&&cJSON_IsNumber(freq)&&cJSON_IsNumber(cap)&&freq->valuedouble==std::floor(freq->valuedouble)&&cap->valuedouble==std::floor(cap->valuedouble)&&freq->valuedouble>=800&&freq->valuedouble<=1000&&cap->valuedouble>=18&&cap->valuedouble<=(unlocked()?30:25);
  if(!ok){cJSON_Delete(j);return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Invalid PSU/search settings or experiment active");}
  Config c;c.watts=w->valuedouble;c.amps=a->valuedouble;c.maximum=uint16_t(freq->valuedouble);c.cap=uint16_t(cap->valuedouble);cJSON_Delete(j);
  nvs_handle_t h;if(nvs_open("af_turbo",NVS_READWRITE,&h)!=ESP_OK)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"storage unavailable");bool saved=nvs_set_blob(h,"config",&c,sizeof(c))==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);if(!saved)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"storage failed");
  config=c;psu_watts=c.watts;psu_amps=c.amps;limit=c.maximum;requested_cap=c.cap;settings::get().power_cap_w=c.cap;settings::save();return httpd_resp_sendstr(req,"PSU and search settings saved; no automatic activation");
 }
 bool valid=cJSON_IsBool(en),enabled=cJSON_IsTrue(en);bool params=cJSON_IsString(confirm)&&!strcmp(confirm->valuestring,"TURBO1000")&&cJSON_IsNumber(freq)&&cJSON_IsNumber(cap)&&std::isfinite(freq->valuedouble)&&std::isfinite(cap->valuedouble)&&freq->valuedouble==std::floor(freq->valuedouble)&&cap->valuedouble==std::floor(cap->valuedouble)&&freq->valuedouble>=800&&freq->valuedouble<=1000&&cap->valuedouble>=18&&cap->valuedouble<=30;
 unsigned f=params?unsigned(freq->valuedouble):0,p=params?unsigned(cap->valuedouble):0;cJSON_Delete(j);
 if(!valid|| (enabled&&(!params||!turbo_math::max_valid(f,p))))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Confirm TURBO1000; maxFreq800..1000; power18..30W");
 if(!enabled){stop(Reason::User);return httpd_resp_sendstr(req,"Stopping in stock tuner");}
 Guard guard;if(!guard.ok)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"turbo unavailable");
 uint16_t sf,sv;float gh,actual;auto observed=hunter::work_snapshot(active_pool());
 if(!unlocked()||engaged()||observed.accepted<100||observed.seconds<1800||g_state.tuner.phase!=TunerPhase::Locked||hunter::benchmark_running()||health()!=Reason::None||!intel::stable_point(sf,sv,gh)||sf>800||!asic::pll_supported(float(f),actual))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Need30min measured stable Gamma point, fresh power/sensors, V1 failover and no running experiment");
 requested_cap=p;limit=f;
 if(g_state.pin>power_budget()*.95f)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Stable point exceeds derated PSU budget");
 fatal_reason=Reason::None;why=Reason::None;cancel=false;state=1;queued=true;return httpd_resp_sendstr(req,"Queued in stock tuner; no forced1000MHz");
}
}

namespace turbo {bool request_search(){if(!unlocked()||engaged())return false;uint16_t f,mv;float gh;auto w=hunter::work_snapshot(active_pool());if(g_state.tuner.phase!=TunerPhase::Locked||w.accepted<100||w.seconds<1800||health()!=Reason::None||!intel::stable_point(f,mv,gh)||f>800||hunter::benchmark_running())return false;fatal_reason=Reason::None;cancel=false;why=Reason::None;state=1;queued=true;return true;}}
