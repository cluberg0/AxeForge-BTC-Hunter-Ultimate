#include "core/intelligence.h"
#include "core/intel_math.h"
#include "core/state.h"
#include "core/settings.h"
#include "core/board.h"
#include "esp_heap_caps.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "cJSON.h"
#include <ctime>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <new>
#include <atomic>
using namespace intelligence;
namespace {
// Versioned because archive records now retain per-metric sample counts.
constexpr uint32_t MAGIC=0x41495832;
constexpr int H=120,D=288,W=8,M=31;
struct Day {uint32_t magic=MAGIC,day=0;Record row[24];};
struct Month {uint32_t magic=MAGIC;Record row[M];};
struct Config {uint32_t magic=MAGIC;uint8_t enabled=0,restore=0,curve[4]={50,55,75,100};};
struct Saved {uint32_t magic=MAGIC;Point point,prior;};
static Record *recent=nullptr,*five=nullptr;
static Day *week=nullptr;
static Month month;
// Task-owned PSRAM scratch avoids multi-kilobyte Day/Month objects on the stack.
static Day *save_day=nullptr;
static Month *save_month=nullptr;
static int rh=0,rn=0,fh=0,fn=0;
static Aggregate a5,ah;
static Config conf;
static Point stable,prior,candidate;
static uint16_t stable_n=0;
static double stable_sum=0;
static uint32_t last_sample=0,last_day=0;
static SemaphoreHandle_t mu=nullptr;
static bool archive_ok=true,task_ok=false;
static std::atomic<bool> floor_on{false};
static bool telemetry_fresh(){uint32_t seen=g_state.telemetry_ms.load();return seen&&uint32_t(esp_timer_get_time()/1000)-seen<=3000;}
static const char *TAG="intel";
struct Guard {bool ok;Guard(unsigned wait=100):ok(mu&&xSemaphoreTake(mu,pdMS_TO_TICKS(wait))==pdTRUE){}~Guard(){if(ok)xSemaphoreGive(mu);}};
static bool valid_time(uint32_t t){return t>=1577836800U&&t<4102444800U;}
static bool read_blob(const char *k,void *p,size_t n){nvs_handle_t h;if(nvs_open("af_intel",NVS_READONLY,&h)!=ESP_OK)return false;size_t z=n;auto e=nvs_get_blob(h,k,p,&z);nvs_close(h);return e==ESP_OK&&z==n;}
static bool write_blob(const char*k,const void*p,size_t n){
 // Keep a whole page available for existing settings/OTA metadata and GC.
 // Refuse a new archive write rather than consume that reserve or erase NVS.
 nvs_stats_t usage{};auto e=nvs_get_stats(nullptr,&usage);
 const size_t reserve=strcmp(k,"config")==0?0:128;
 if(e!=ESP_OK||usage.free_entries<(n+31)/32+reserve+4){ESP_LOGW(TAG,"archive write %s refused: NVS reserve",k);return false;}
 nvs_handle_t h;e=nvs_open("af_intel",NVS_READWRITE,&h);if(e==ESP_OK){e=nvs_set_blob(h,k,p,n);if(e==ESP_OK)e=nvs_commit(h);nvs_close(h);}if(e!=ESP_OK)ESP_LOGW(TAG,"archive write %s: %s (no erase)",k,esp_err_to_name(e));return e==ESP_OK;}
static void mark_io(bool ok){Guard g;if(g.ok&&!ok)archive_ok=false;}
static bool row_ok(const Record&r){return valid_time(r.time)&&r.n>0&&r.n<=2880&&(r.step==30||r.step==300||r.step==3600||r.step==86400);}
static void ring_add(Record *r,int cap,int &head,int &count,const Record&v){r[head]=v;head=(head+1)%cap;if(count<cap)count++;}
static void values(float *v){if(!telemetry_fresh()){for(unsigned i=0;i<N;i++)v[i]=NAN;return;}const bool mining=g_state.status==SysStatus::Mining;auto set=[&](unsigned i,float n,float lo,float hi){v[i]=range(n,lo,hi)?n:NAN;};
 v[0]=mining&&hash_ok(g_state.hashrate_ghs)?g_state.hashrate_ghs:NAN;
 set(1,g_state.temp_ok?g_state.chip_temp_max:NAN,0,110);set(2,g_state.vr_temp_ok?g_state.vr_temp:NAN,0,130);
 set(3,g_state.pin,0,50);set(4,g_state.fan_pct,0,100);set(5,g_state.freq_mhz,0,800);set(6,g_state.core_mv,0,1300);set(7,mining?g_state.error_pct:NAN,0,100);set(8,g_state.fan_rpm[0],0,50000);set(9,g_state.vin,0,6);set(10,g_state.vout,0,2);
 // Do not mix network difficulty of arbitrary alternative coins into BTC history.
 v[11]=NAN; if(mining&&(!strcmp(g_state.pool_host,"stratum.bitaxe.de")||!strcmp(g_state.pool_host,"stratum.ckpool.org"))){uint32_t n=g_state.network_nbits,m=n&0x007fffff;int e=int(n>>24);if(m&&!(n&0x00800000)&&e>=3&&e<=32){double d=std::ldexp(65535.0/m,8*(29-e));if(d>0&&d<1e20)v[11]=float(d);}}
 v[12]=std::isfinite(v[0])&&v[0]>0&&std::isfinite(v[3])?v[3]*1000/v[0]:NAN;
}
static Record rollup(const Day&d){Aggregate a;for(auto&r:d.row)if(row_ok(r)&&r.time/86400==d.day){float v[N];for(unsigned i=0;i<N;i++)v[i]=i==11?r.diff:decode(r.x[i],i); // weighted hourly means, bounded by 120 samples/hour
 unsigned n=std::min<unsigned>(r.n,120);a.bucket=d.day*86400;a.n+=n;for(unsigned i=0;i<N;i++)if(std::isfinite(v[i])){unsigned count=std::min<unsigned>(r.observed[i],n);a.sum[i]+=double(v[i])*count;a.cnt[i]+=count;}}return a.finish(86400);}
static void load(){for(int i=0;i<W;i++){char k[8];snprintf(k,sizeof(k),"d%d",i);auto &d=week[i];if(!read_blob(k,&d,sizeof(d))||d.magic!=MAGIC||d.day%W!=unsigned(i)||!valid_time(d.day*86400U))d=Day{};}
 if(!read_blob("month",&month,sizeof(month))||month.magic!=MAGIC)month=Month{};
 for(int wi=0;wi<W;wi++){auto &d=week[wi];if(d.day){auto r=rollup(d);if(row_ok(r))month.row[d.day%M]=r;if(d.day>last_day)last_day=d.day;}}
 Config c;if(read_blob("config",&c,sizeof(c))&&c.magic==MAGIC&&c.enabled<=1&&c.restore<=1&&curve_ok(c.curve))conf=c;
 Saved s;if(read_blob("stable",&s,sizeof(s))&&s.magic==MAGIC&&valid_point(s.point)){stable=s.point;if(valid_point(s.prior))prior=s.prior;}
}
static void sample(uint32_t now){if(!g_state.time_synced||!valid_time(now))return;float v[N];values(v);uint32_t b5=now/300*300,bh=now/3600*3600;bool wh=false,wm=false,ws=false;Saved sp;
 {Guard g;if(!g.ok)return;if(last_sample&&now<=last_sample){if(last_sample-now<120)return;a5=Aggregate{};ah=Aggregate{};rh=rn=fh=fn=0;stable_n=0;stable_sum=0;last_sample=0;}bool gap=last_sample&&now-last_sample>65;last_sample=now;Aggregate one;one.add(now,v);ring_add(recent,H,rh,rn,one.finish());
 if(a5.bucket&&a5.bucket!=b5){ring_add(five,D,fh,fn,a5.finish(300));a5=Aggregate{};}a5.add(b5,v);
 if(ah.bucket&&ah.bucket!=bh){Record r=ah.finish(3600);uint32_t day=r.time/86400;auto&d=week[day%W];if(d.day!=day){d=Day{};d.day=day;}d.row[(r.time%86400)/3600]=r;*save_day=d;wh=true;auto daily=rollup(d);if(row_ok(daily))month.row[day%M]=daily;
 if(last_day&&last_day!=day){*save_month=month;wm=true;}last_day=day;ah=Aggregate{};}ah.add(bh,v);
 const auto&cfg=settings::get();Point p{g_state.freq_mhz,g_state.core_mv,cfg.power_cap_w,0,now};
 bool good=cfg.autotune&&cfg.tune_goal==1&&cfg.power_cap_w>0&&cfg.power_cap_w<=30&&g_state.tuner.phase==TunerPhase::Locked&&g_state.status==SysStatus::Mining&&g_state.pool_connected&&g_state.temp_ok&&g_state.vr_temp_ok&&g_state.fan_present[0]&&g_state.fan_rpm[0]>300&&range(v[0],1,4000)&&g_state.expected_ghs>0&&v[0]>=g_state.expected_ghs*.92f&&range(v[7],0,.999f)&&range(v[1],0,64.9f)&&range(v[2],0,74.9f)&&range(v[3],0,float(cfg.power_cap_w))&&range(v[9],4.75f,5.5f);
 if(!good||gap||!same_point(p,candidate)){stable_n=0;stable_sum=0;candidate=p;}
 if(good){if(stable_n<61){stable_n++;stable_sum+=v[0];}if(stable_n==61){p.ghs=uint16_t(stable_sum/stable_n);if(valid_point(p)&&!same_point(p,stable)){if(valid_point(stable)&&stable.cap==p.cap&&stable.mhz<p.mhz)prior=stable;else if(prior.cap!=p.cap||prior.mhz>=p.mhz)prior=Point{};stable=p;sp.point=p;sp.prior=prior;ws=true;}}}
 }
 if(wh){char k[8];snprintf(k,sizeof(k),"d%u",unsigned(save_day->day%W));mark_io(write_blob(k,save_day,sizeof(*save_day)));}if(wm)mark_io(write_blob("month",save_month,sizeof(*save_month)));if(ws)mark_io(write_blob("stable",&sp,sizeof(sp)));
}
static void task(void*){for(;;){vTaskDelay(pdMS_TO_TICKS(30000));sample(uint32_t(time(nullptr)));}}
static esp_err_t chunk(httpd_req_t*r,const char*s){return httpd_resp_send_chunk(r,s,strlen(s));}
static void num(char *dst,size_t n,float x){if(std::isfinite(x))snprintf(dst,n,"%.6g",double(x));else snprintf(dst,n,"null");}
static esp_err_t row_json(httpd_req_t*r,const Record&v,bool comma){char a[N][24];for(unsigned i=0;i<N;i++)num(a[i],sizeof(a[i]),i==11?v.diff:decode(v.x[i],i));char b[512]; // row schema of RU-FIX 9, time in ms, TH/s, voltage in mV as applicable
 char hr[24],mv[24];num(hr,sizeof(hr),decode(v.x[0],0)/1000);num(mv,sizeof(mv),decode(v.x[10],10)*1000);
 snprintf(b,sizeof(b),"%s[%llu,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,null,null,null,%s,%s,%s,\"%s\",%u,%u]",comma?",":"",(unsigned long long)v.time*1000,hr,a[1],a[2],a[3],a[12],a[4],a[5],a[6],a[7],a[11],a[8],a[9],mv,std::isfinite(v.diff)?"BTC":"",unsigned(v.n),unsigned(v.step));return chunk(r,b);}
}
namespace intel {
void start(){recent=(Record*)heap_caps_calloc(H,sizeof(Record),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);five=(Record*)heap_caps_calloc(D,sizeof(Record),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);week=(Day*)heap_caps_calloc(W,sizeof(Day),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);save_day=(Day*)heap_caps_malloc(sizeof(Day),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);save_month=(Month*)heap_caps_malloc(sizeof(Month),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);if(!recent||!five||!week||!save_day||!save_month){free(recent);free(five);free(week);free(save_day);free(save_month);recent=five=nullptr;week=nullptr;save_day=nullptr;save_month=nullptr;ESP_LOGE(TAG,"no PSRAM; intelligence disabled");return;}for(int i=0;i<H;i++)new(&recent[i]) Record{};for(int i=0;i<D;i++)new(&five[i]) Record{};for(int i=0;i<W;i++)new(&week[i]) Day{};mu=xSemaphoreCreateMutex();if(!mu){free(recent);free(five);free(week);free(save_day);free(save_month);recent=five=nullptr;week=nullptr;save_day=nullptr;save_month=nullptr;ESP_LOGE(TAG,"no mutex; intelligence disabled");return;}load();floor_on.store(conf.enabled);task_ok=xTaskCreate(task,"intel",6144,nullptr,2,nullptr)==pdPASS;if(!task_ok){ESP_LOGE(TAG,"no task; archive disabled");archive_ok=false;conf.enabled=conf.restore=0;floor_on.store(false);}}
float fan_floor(){if(!floor_on.load())return 0;if(!telemetry_fresh())return 100;Config c;{Guard g(0);if(!g.ok)return mu?100:0;c=conf;}if(!c.enabled)return 0;return curve_floor(g_state.temp_ok?g_state.chip_temp_max:NAN,g_state.vr_temp_ok?g_state.vr_temp:NAN,c.curve);}
bool rollback_point(uint16_t cf,uint16_t cm,uint16_t nf,uint16_t cap,uint16_t &f,uint16_t &mv){Guard g;if(!g.ok||!task_ok||!conf.restore||!telemetry_fresh())return false;const Point p=fallback(stable,cf,cm,nf,cap)?stable:prior;if(!fallback(p,cf,cm,nf,cap))return false;if(!g_state.temp_ok||!g_state.vr_temp_ok||!range(g_state.chip_temp_max,0,64.9)||!range(g_state.vr_temp,0,74.9)||!range(g_state.pin,0,cap)||!range(g_state.vin,4.75,5.5))return false;f=p.mhz;mv=p.mv;return true;}
esp_err_t get(httpd_req_t*req){char q[32],v[16];unsigned sec=3600;if(httpd_req_get_url_query_str(req,q,sizeof(q))==ESP_OK&&httpd_query_key_value(q,"range",v,sizeof(v))==ESP_OK){unsigned z=unsigned(strtoul(v,nullptr,10));if(z==3600||z==86400||z==604800||z==2592000)sec=z;}
 const int cap=D+W*24+M;Record *rows=(Record*)heap_caps_malloc(sizeof(Record)*cap,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);if(!rows)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"no memory");int count=0;Config c;Point p;uint16_t sn;bool io;uint32_t last;{Guard g;if(!g.ok){free(rows);return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"busy");}c=conf;p=stable;sn=stable_n;io=archive_ok;last=last_sample;
 auto add=[&](const Record&r){if(row_ok(r)&&count<cap)rows[count++]=r;};
 if(sec==3600){for(int i=0;i<rn;i++)add(recent[(rh-rn+i+H)%H]);}
 else if(sec==86400){uint32_t first=fn?five[(fh-fn+D)%D].time:0;for(int wi=0;wi<W;wi++) for(auto&r:week[wi].row)if(!first||r.time+3600<=first)add(r);for(int i=0;i<fn;i++)add(five[(fh-fn+i+D)%D]);if(a5.n)add(a5.finish(300));}
 else if(sec==604800){for(int wi=0;wi<W;wi++) for(auto&r:week[wi].row)add(r);if(ah.n)add(ah.finish(3600));}
 else {for(auto&r:month.row)add(r);}
 }
 uint32_t now=uint32_t(time(nullptr));std::sort(rows,rows+count,[](const Record&a,const Record&b){return a.time<b.time;});httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");char h[512];snprintf(h,sizeof(h),"{\"native\":true,\"time\":%u,\"last\":%u,\"archiveOk\":%s,\"enabled\":%s,\"restore\":%s,\"curve\":[%u,%u,%u,%u],\"stableSamples\":%u,\"point\":[%u,%u,%u,%u,%u],\"rows\":[",now,last,io?"true":"false",c.enabled?"true":"false",c.restore?"true":"false",c.curve[0],c.curve[1],c.curve[2],c.curve[3],sn,p.mhz,p.mv,p.cap,p.ghs,p.time);esp_err_t e=chunk(req,h);bool comma=false;for(int i=0;e==ESP_OK&&i<count;i++)if(rows[i].time<=now&&now-rows[i].time<=sec){e=row_json(req,rows[i],comma);comma=true;}free(rows);if(e!=ESP_OK)return e;e=chunk(req,"]}");return e==ESP_OK?httpd_resp_send_chunk(req,nullptr,0):e;}
esp_err_t set(httpd_req_t*req){if(!mu||!task_ok)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"intelligence unavailable");if(req->content_len<=0||req->content_len>256)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"invalid body");char b[257];int got=0;while(got<req->content_len){int n=httpd_req_recv(req,b+got,req->content_len-got);if(n<=0)return ESP_FAIL;got+=n;}b[got]=0;cJSON*j=cJSON_Parse(b);if(!j)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"bad json");Config c;auto *on=cJSON_GetObjectItem(j,"enabled"),*a=cJSON_GetObjectItem(j,"curve"),*restore=cJSON_GetObjectItem(j,"restore");bool ok=cJSON_IsBool(on)&&cJSON_IsBool(restore)&&cJSON_IsArray(a)&&cJSON_GetArraySize(a)==4;c.enabled=cJSON_IsTrue(on);c.restore=cJSON_IsTrue(restore);for(int i=0;ok&&i<4;i++){auto*x=cJSON_GetArrayItem(a,i);ok=cJSON_IsNumber(x)&&x->valuedouble>=50&&x->valuedouble<=100&&x->valuedouble==x->valueint;if(ok)c.curve[i]=x->valueint;}cJSON_Delete(j);if(!ok||!curve_ok(c.curve))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"invalid curve");{Guard g;if(!g.ok)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"busy");if(!write_blob("config",&c,sizeof(c))){archive_ok=false;return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"storage failed");}conf=c;floor_on.store(c.enabled);}return httpd_resp_sendstr(req,"OK");}
}
