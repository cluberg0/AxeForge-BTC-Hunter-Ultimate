#include "hunter.h"
#include "hunter_math.h"
#include "core/state.h"
#include "core/settings.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"
#include "net/notify.h"
#include "cJSON.h"
#include "core/json_util.h"
#include <cstdio>
#include <cstring>
#include <cmath>
#include <cstdlib>
#include <cstdarg>
namespace hunter {
namespace {
constexpr int N=4, PENDING=64;
constexpr uint32_t WINDOW=1800;
struct Request {uint32_t id=0; double diff=0; int64_t time=0; bool valid=false,btc=false,timed_out=false,candidate=false;uint32_t trial_id=0;uint8_t stage=0;};
struct Pool {Request pending[PENDING];unsigned cursor=0;double work=0,btc_work=0;uint32_t btc_accepted=0,accepted=0,rejected=0,missed=0,failed=0,clean_n=0,clean_ms=0,max_ms=0,gen=0;bool gen_valid=false;};
struct Candidate {uint32_t version=1,id=0;int pool=-1;uint8_t state=0;char hash[65]={};};
// state: 1 queued, 2 sent, 3 accepted, 4 rejected, 5 failed, 6 lost response, 7 SV2 sent (unconfirmed).
struct Trial {uint8_t state=0,stage=0;uint16_t freq=0,mv=0,base=0,cap=0;uint32_t vr=0;int pool=-1;int64_t start=0,last_check=0;float chip=0,vr_temp=0;double work[3]={},work2[3]={},elapsed[3]={},rate[3]={};uint32_t id=0,replies[3]={},rejected[3]={};};
Pool ps[N];Candidate last;Trial trial;portMUX_TYPE mux=portMUX_INITIALIZER_UNLOCKED;bool dirty=false;bool persisted=true;bool candidate_live=false;bool task_ok=false;int64_t boot=0,next_save=0,healthy_since=0;uint32_t trial_sequence=0;int warm_pool=-1;uint16_t warm_freq=0,warm_mv=0,warm_cap=0;
constexpr uint16_t steps[3]={500,350,250};
bool valid_pool(int p){return p>=0&&p<N;}
bool known_btc(int p){return valid_pool(p)&&(!strcmp(g_state.pools[p].host,"stratum.bitaxe.de")||!strcmp(g_state.pools[p].host,"stratum.ckpool.org"));}
bool hash_ok(const char *s){if(!s||strlen(s)!=64)return false;for(unsigned i=0;i<64;i++)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')||(s[i]>='A'&&s[i]<='F')))return false;return true;}
void cand(int pool,uint32_t id,const char *hash,uint8_t state){last=Candidate{};last.pool=pool;last.id=id;last.state=state;if(hash_ok(hash))memcpy(last.hash,hash,65);dirty=true;persisted=false;candidate_live=state==1;}
int active_pool(){int result=-1;for(int i=0;i<N;i++)if(g_state.pools[i].enabled&&g_state.pools[i].connected&&!g_state.pools[i].payout_blocked&&g_state.pools[i].work_pct==100){if(result>=0)return -1;result=i;}return result;}
bool healthy(){auto &c=settings::get();uint32_t sample=g_state.telemetry_ms.load(),counter=g_state.hash_counter_ms.load(),now=uint32_t(esp_timer_get_time()/1000);return sample&&counter&&now-sample<=3000&&now-counter<=10000&&g_state.status==SysStatus::Mining&&g_state.pool_connected&&g_state.temp_ok&&g_state.vr_temp_ok&&g_state.tuner.phase==TunerPhase::Locked&&g_state.chip_temp_max<65&&g_state.vr_temp<75&&g_state.vin>=4.75&&g_state.vin<=5.5&&g_state.error_pct>=0&&g_state.error_pct<1&&g_state.fan_present[0]&&g_state.fan_rpm[0]>300&&hunter_math::rate_ok(g_state.hashrate_ghs)&&g_state.expected_ghs>0&&g_state.hashrate_ghs>=g_state.expected_ghs*.92&&c.autotune&&c.tune_goal==1&&c.power_cap_w>0&&c.power_cap_w<=30&&g_state.pin>0&&g_state.pin<=c.power_cap_w&&c.pool_mode==PoolMode::Failover;}
void tick(){int p=active_pool();bool ok=healthy();const auto &c=settings::get();int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);
 if(ok&&p>=0){if(!healthy_since||warm_pool!=p||warm_freq!=g_state.freq_mhz||warm_mv!=g_state.core_mv||warm_cap!=c.power_cap_w){healthy_since=now;warm_pool=p;warm_freq=g_state.freq_mhz;warm_mv=g_state.core_mv;warm_cap=c.power_cap_w;}}else healthy_since=0;
 if(trial.state==1){trial.last_check=now;if(!ok||p!=trial.pool||c.job_ms!=trial.base||c.vr_hz!=trial.vr||c.power_cap_w!=trial.cap||g_state.freq_mhz!=trial.freq||g_state.core_mv!=trial.mv||fabsf(g_state.chip_temp_max-trial.chip)>5||fabsf(g_state.vr_temp-trial.vr_temp)>5){trial.state=3;}
 else if(now-trial.start>=WINDOW*1000000LL){unsigned s=trial.stage;trial.elapsed[s]=(now-trial.start)/1e6;trial.rate[s]=hunter_math::ghs(trial.work[s],trial.elapsed[s]);if(trial.replies[s]<100){trial.state=3;}else if(s==2){trial.state=2;}else{trial.stage++;trial.start=now;}}}
 // Mark unanswered submissions once, including ordinary shares. Retain entries
 // until eviction/disconnect so a late ACK can still be associated correctly.
 for(int i=0;i<N;i++)for(auto &r:ps[i].pending)if(r.valid&&!r.timed_out&&now-r.time>120000000LL){r.timed_out=true;ps[i].missed++;if(candidate_live&&last.pool==i&&last.id==r.id&&(last.state==1||last.state==2)){last.state=6;dirty=true;persisted=false;}}
 Candidate copy=last;bool save=dirty&&now>=next_save;if(save)dirty=false;portEXIT_CRITICAL(&mux);
 if(save){nvs_handle_t h;bool good=false;if(nvs_open("af_hunter",NVS_READWRITE,&h)==ESP_OK){good=nvs_set_blob(h,"candidate",&copy,sizeof(copy))==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);}portENTER_CRITICAL(&mux);persisted=good&&!dirty;if(!good){dirty=true;next_save=now+60000000LL;}else next_save=0;portEXIT_CRITICAL(&mux);}
}
void task(void*){while(true){vTaskDelay(pdMS_TO_TICKS(5000));tick();}}
}
void start(){boot=esp_timer_get_time();nvs_handle_t h;if(nvs_open("af_hunter",NVS_READONLY,&h)==ESP_OK){Candidate c;size_t n=sizeof(c);if(nvs_get_blob(h,"candidate",&c,&n)==ESP_OK&&n==sizeof(c)&&c.version==1&&c.state<=7&&valid_pool(c.pool)){c.hash[64]=0;if(!hash_ok(c.hash))c.hash[0]=0;if(c.state==1||c.state==2)c.state=6;last=c;}nvs_close(h);}task_ok=xTaskCreate(task,"btc_hunter",4096,nullptr,2,nullptr)==pdPASS;if(!task_ok)ESP_LOGE("hunter","task start failed");}
void job_sent(int p,uint32_t gen,int64_t received,bool clean){if(!valid_pool(p)||!clean||received<=0)return;int64_t us=esp_timer_get_time()-received;if(us<0||us>60000000)return;uint32_t ms=us/1000;portENTER_CRITICAL(&mux);auto &m=ps[p];if(!m.gen_valid||m.gen!=gen){m.gen_valid=true;m.gen=gen;m.clean_ms=m.clean_n?(m.clean_ms*7+ms)/8:ms;m.clean_n++;if(ms>m.max_ms)m.max_ms=ms;}portEXIT_CRITICAL(&mux);}
void submitted(int p,uint32_t id,double diff,bool candidate,const char *hash){if(!valid_pool(p))return;int64_t now=esp_timer_get_time();bool btc=known_btc(p);portENTER_CRITICAL(&mux);auto &m=ps[p];auto &r=m.pending[m.cursor++%PENDING];if(r.valid){if(!r.timed_out)m.missed++;if(candidate_live&&last.pool==p&&last.id==r.id&&(last.state==1||last.state==2||last.state==6)){last.state=6;dirty=true;persisted=false;candidate_live=false;}}r=Request{};r.id=id;r.diff=std::isfinite(diff)&&diff>0&&diff<=std::ldexp(1.,224)?diff:0;r.time=now;r.valid=true;r.btc=btc;r.candidate=candidate;if(trial.state==1&&trial.pool==p){r.trial_id=trial.id;r.stage=trial.stage;}if(candidate)cand(p,id,hash,1);portEXIT_CRITICAL(&mux);}
void sent(int p,uint32_t id,bool ok){if(!valid_pool(p))return;portENTER_CRITICAL(&mux);auto &m=ps[p];bool pending=false;for(auto &r:m.pending)if(r.valid&&r.id==id){pending=true;if(!ok){r.valid=false;m.failed++;}break;}
 // An ACK may arrive on the reader task before send_line returns. In that
 // case reply() already owns the outcome; do not overwrite it or count failure.
 if(pending&&candidate_live&&last.pool==p&&last.id==id&&last.state==1){last.state=ok?2:5;dirty=true;persisted=false;if(!ok)candidate_live=false;}portEXIT_CRITICAL(&mux);}
double reply(int p,uint32_t id,bool ok,bool *matched){if(matched)*matched=false;if(!valid_pool(p))return 0;double credited=0;bool candidate_reply=false;char hash[65]={};portENTER_CRITICAL(&mux);auto &m=ps[p];bool found=false;for(auto &r:m.pending)if(r.valid&&r.id==id){found=true;if(ok){m.accepted++;m.work+=r.diff;credited=r.diff;if(r.btc){m.btc_work+=r.diff;m.btc_accepted++;}}else m.rejected++;
 if(r.trial_id&&r.trial_id==trial.id&&r.stage<3&&(trial.state==1||trial.state==2)){auto s=r.stage;if(ok){trial.work[s]+=r.diff;trial.work2[s]+=r.diff*r.diff;trial.replies[s]++;if(trial.elapsed[s]>0)trial.rate[s]=hunter_math::ghs(trial.work[s],trial.elapsed[s]);}else trial.rejected[s]++;}
 candidate_reply=r.candidate;r.valid=false;break;}if(found&&candidate_live&&last.pool==p&&last.id==id&&(last.state==1||last.state==2||last.state==6)){last.state=ok?3:4;dirty=true;persisted=false;candidate_live=false;memcpy(hash,last.hash,sizeof(hash));}portEXIT_CRITICAL(&mux);if(matched)*matched=found;if(candidate_reply){ESP_LOGW("hunter","candidate id %lu %s: %s by pool %d",(unsigned long)id,hash,ok?"accepted":"rejected",p+1);notify::post(NOTIFY_BLOCK,"BLOCK CANDIDATE id %lu %s by pool %d: %s (not chain confirmation)",(unsigned long)id,ok?"accepted":"rejected",p+1,hash);}return credited;}
void disconnected(int p){if(!valid_pool(p))return;portENTER_CRITICAL(&mux);for(auto &r:ps[p].pending)if(r.valid){r.valid=false;if(!r.timed_out)ps[p].missed++;}if(candidate_live&&last.pool==p&&(last.state==1||last.state==2||last.state==6)){last.state=6;dirty=true;persisted=false;candidate_live=false;}if(trial.state==1&&trial.pool==p)trial.state=3;portEXIT_CRITICAL(&mux);}
void sv2_candidate(int p,const char *hash,bool ok){if(!valid_pool(p))return;portENTER_CRITICAL(&mux);cand(p,0,hash,ok?7:5);portEXIT_CRITICAL(&mux);}
void unavailable_candidate(int p,const char *hash){if(!valid_pool(p))return;portENTER_CRITICAL(&mux);cand(p,0,hash,5);portEXIT_CRITICAL(&mux);}
uint16_t interval(uint16_t configured){int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);if(trial.state==1&&(configured!=trial.base||now-trial.last_check>15000000LL))trial.state=3;uint16_t out=trial.state==1?steps[trial.stage]:configured;portEXIT_CRITICAL(&mux);return out;}
namespace {
bool append_json(char *buf,size_t capacity,size_t &used,const char *format,...){if(used>=capacity)return false;va_list args;va_start(args,format);int written=vsnprintf(buf+used,capacity-used,format,args);va_end(args);if(written<0||size_t(written)>=capacity-used)return false;used+=size_t(written);return true;}
}
esp_err_t get(httpd_req_t *req){
 struct Row{double work,btc;uint32_t ba,a,r,miss,failed,n,ms,max;};Row rows[N];Candidate c;Trial t;bool saved;int64_t now=esp_timer_get_time();
 portENTER_CRITICAL(&mux);for(int i=0;i<N;i++){auto &m=ps[i];rows[i]={m.work,m.btc_work,m.btc_accepted,m.accepted,m.rejected,m.missed,m.failed,m.clean_n,m.clean_ms,m.max_ms};}c=last;t=trial;saved=persisted;portEXIT_CRITICAL(&mux);
 // Keep the web-server stack bounded and reject overflow rather than emitting
 // partial JSON or passing an underflowed length to snprintf.
 constexpr size_t capacity=4096;char *buf=(char*)malloc(capacity);if(!buf)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"no memory");size_t n=0;
 bool good=append_json(buf,capacity,n,"{\"native\":true,\"taskOk\":%s,\"seconds\":%.0f,\"pools\":[",task_ok?"true":"false",(now-boot)/1e6);
 for(int i=0;good&&i<N;i++){auto &r=rows[i];good=append_json(buf,capacity,n,"%s{\"work\":%.8g,\"btcWork\":%.8g,\"btcAccepted\":%lu,\"accepted\":%lu,\"rejected\":%lu,\"missing\":%lu,\"failed\":%lu,\"cleanN\":%lu,\"cleanMs\":%lu,\"cleanMax\":%lu}",i?",":"",r.work,r.btc,(unsigned long)r.ba,(unsigned long)r.a,(unsigned long)r.r,(unsigned long)r.miss,(unsigned long)r.failed,(unsigned long)r.n,(unsigned long)r.ms,(unsigned long)r.max);}
 double low[3]={},high[3]={};for(unsigned i=0;i<3;i++){double neff=t.work2[i]>0?t.work[i]*t.work[i]/t.work2[i]:0;double delta=neff>0?1.96/std::sqrt(neff):1;low[i]=t.rate[i]*std::fmax(0.,1-delta);high[i]=t.rate[i]*(1+delta);}
 good=good&&append_json(buf,capacity,n,"],\"candidate\":{\"state\":%u,\"pool\":%d,\"hash\":\"%s\",\"persisted\":%s},\"trial\":{\"state\":%u,\"stage\":%u,\"elapsed\":%.0f,\"uncertain\":true,\"rates\":[%.3f,%.3f,%.3f],\"ci95Low\":[%.3f,%.3f,%.3f],\"ci95High\":[%.3f,%.3f,%.3f],\"accepted\":[%lu,%lu,%lu],\"rejected\":[%lu,%lu,%lu]}}",c.state,c.pool,c.hash,saved?"true":"false",t.state,t.stage,t.state==1?(now-t.start)/1e6:0,t.rate[0],t.rate[1],t.rate[2],low[0],low[1],low[2],high[0],high[1],high[2],(unsigned long)t.replies[0],(unsigned long)t.replies[1],(unsigned long)t.replies[2],(unsigned long)t.rejected[0],(unsigned long)t.rejected[1],(unsigned long)t.rejected[2]);
 if(!good){free(buf);return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"response too large");}httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");auto result=httpd_resp_sendstr(req,buf);free(buf);return result;
}
esp_err_t set(httpd_req_t *req){char body[128];if(req->content_len<=0||(size_t)req->content_len>=sizeof(body))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"bad body");int got=0;while(got<(int)req->content_len){int n=httpd_req_recv(req,body+got,req->content_len-got);if(n<=0)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"incomplete");got+=n;}body[got]=0;cJSON *j=json_parse(body);if(!j)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"bad json");auto *s=cJSON_GetObjectItem(j,"start");bool valid=cJSON_IsBool(s),go=cJSON_IsTrue(s);cJSON_Delete(j);if(!valid)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"start bool required");int p=active_pool();auto &cfg=settings::get();bool ok=task_ok&&healthy()&&p>=0&&g_state.pools[p].proto<=1&&cfg.vr_hz==0&&(!cfg.job_ms||cfg.job_ms==500);int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);if(go&&(!healthy_since||now-healthy_since<WINDOW*1000000LL))ok=false;if(!go){if(trial.state==1)trial.state=3;}else if(ok&&trial.state!=1){trial=Trial{};if(++trial_sequence==0)++trial_sequence;trial.id=trial_sequence;trial.state=1;trial.pool=p;trial.chip=g_state.chip_temp_max;trial.vr_temp=g_state.vr_temp;trial.freq=g_state.freq_mhz;trial.mv=g_state.core_mv;trial.base=cfg.job_ms;trial.vr=cfg.vr_hz;trial.cap=cfg.power_cap_w;trial.start=trial.last_check=now;}else ok=false;portEXIT_CRITICAL(&mux);if(go&&!ok)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Need 30 min stable capped auto-tune, one V1 pool, default timing, no running test");return httpd_resp_sendstr(req,"OK");}
}
