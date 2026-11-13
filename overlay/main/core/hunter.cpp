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
constexpr uint32_t WINDOW=1800,WARMUP=300;
constexpr unsigned STAGES=6;
constexpr uint8_t order[STAGES]={0,1,2,2,1,0};
struct Request {uint32_t id=0; double diff=0; int64_t time=0; bool valid=false,btc=false,timed_out=false,candidate=false,measured=false;uint32_t trial_id=0;uint8_t stage=0;};
struct Pool {Request pending[PENDING];uint64_t connected_ms=0,disconnected_ms=0,unobserved_ms=0;bool observed=false,was_enabled=false,was_connected=false;unsigned cursor=0;double work=0,btc_work=0,squared=0;uint32_t btc_accepted=0,accepted=0,rejected=0,missed=0,failed=0,clean_n=0,clean_ms=0,max_ms=0,gen=0;bool gen_valid=false;};
struct Candidate {uint32_t version=2,id=0;int pool=-1;uint8_t state=0,btc=0;char hash[65]={};};
// state: 1 queued, 2 sent, 3 accepted, 4 rejected, 5 failed, 6 lost response, 7 SV2 sent (unconfirmed).
enum class Abort:uint8_t {None,User,Safety,Pool,Config,Temperature,Samples,Controller,Transport,Replies};
struct Trial {uint8_t state=0,stage=0;bool measuring=false;Abort reason=Abort::None;uint16_t freq=0,mv=0,base=0,cap=0;uint32_t vr=0;int pool=-1;int64_t start=0,last_check=0;float chip=0,vr_temp=0;double work[STAGES]={},work2[STAGES]={},elapsed[STAGES]={},rate[STAGES]={};uint32_t id=0,replies[STAGES]={},rejected[STAGES]={},warm_replies[STAGES]={},warm_rejected[STAGES]={};};
Pool ps[N];Candidate last;Trial trial;portMUX_TYPE mux=portMUX_INITIALIZER_UNLOCKED;bool dirty=false;bool persisted=true;bool candidate_live=false;bool task_ok=false;int64_t boot=0,next_save=0,healthy_since=0,last_observation=0;uint32_t trial_sequence=0;int warm_pool=-1;uint16_t warm_freq=0,warm_mv=0,warm_cap=0;
constexpr uint16_t steps[3]={500,350,250};
bool valid_pool(int p){return p>=0&&p<N;}
bool hash_ok(const char *s){if(!s||strlen(s)!=64)return false;for(unsigned i=0;i<64;i++)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')||(s[i]>='A'&&s[i]<='F')))return false;return true;}
void cand(int pool,uint32_t id,const char *hash,uint8_t state,bool btc){last=Candidate{};last.pool=pool;last.id=id;last.state=state;last.btc=btc;if(hash_ok(hash))memcpy(last.hash,hash,65);dirty=true;persisted=false;candidate_live=state==1;}
int active_pool(){int result=-1;for(int i=0;i<N;i++)if(g_state.pools[i].enabled&&g_state.pools[i].connected&&!g_state.pools[i].payout_blocked&&g_state.pools[i].work_pct==100){if(result>=0)return -1;result=i;}return result;}
bool healthy(){auto &c=settings::get();uint32_t sample=g_state.telemetry_ms.load(),counter=g_state.hash_counter_ms.load(),now=uint32_t(esp_timer_get_time()/1000);return sample&&counter&&now-sample<=3000&&now-counter<=10000&&g_state.status==SysStatus::Mining&&g_state.pool_connected&&g_state.temp_ok&&g_state.vr_temp_ok&&g_state.tuner.phase==TunerPhase::Locked&&g_state.chip_temp_max<65&&g_state.vr_temp<75&&g_state.vin>=4.75&&g_state.vin<=5.5&&g_state.error_pct>=0&&g_state.error_pct<1&&g_state.fan_present[0]&&g_state.fan_rpm[0]>300&&hunter_math::rate_ok(g_state.hashrate_ghs)&&g_state.expected_ghs>0&&g_state.hashrate_ghs>=g_state.expected_ghs*.92&&c.autotune&&c.tune_goal==1&&c.power_cap_w>0&&c.power_cap_w<=30&&g_state.pin>0&&g_state.pin<=c.power_cap_w&&c.pool_mode==PoolMode::Failover;}
void abort_trial(Abort reason){if(trial.state==1){if(trial.measuring&&trial.elapsed[trial.stage]==0){trial.elapsed[trial.stage]=double(esp_timer_get_time()-trial.start)/1e6;trial.rate[trial.stage]=hunter_math::ghs(trial.work[trial.stage],trial.elapsed[trial.stage]);}trial.state=3;trial.reason=reason;}}
const char *abort_name(Abort reason){switch(reason){case Abort::User:return "user";case Abort::Safety:return "safety_or_telemetry";case Abort::Pool:return "pool_changed";case Abort::Config:return "configuration_changed";case Abort::Temperature:return "temperature_drift";case Abort::Samples:return "insufficient_samples";case Abort::Controller:return "controller_timeout";case Abort::Transport:return "transport_failure";case Abort::Replies:return "reply_loss_or_rejections";default:return "none";}}
struct TrialSummary {double low[3]={},high[3]={},rates[3]={},stage_rates[STAGES]={};uint32_t accepted[3]={},rejected[3]={};unsigned repeats[3]={};};
TrialSummary summarize_trial(const Trial &t,int64_t now){
 TrialSummary out;double work[3]={},squares[3]={},elapsed[3]={};
 for(unsigned stage=0;stage<STAGES;stage++){unsigned option=order[stage];double seconds=t.elapsed[stage];if(t.state==1&&t.measuring&&stage==t.stage)seconds=(now-t.start)/1e6;out.stage_rates[stage]=hunter_math::ghs(t.work[stage],seconds);work[option]+=t.work[stage];squares[option]+=t.work2[stage];elapsed[option]+=seconds;out.accepted[option]+=t.replies[stage];out.rejected[option]+=t.rejected[stage];if(t.elapsed[stage]>=WINDOW&&t.replies[stage]>=100)out.repeats[option]++;}
 for(unsigned option=0;option<3;option++){out.rates[option]=hunter_math::ghs(work[option],elapsed[option]);double neff=squares[option]>0?work[option]*work[option]/squares[option]:0;double delta=neff>0?out.rates[option]*1.96/std::sqrt(neff):out.rates[option];if(out.repeats[option]==2){unsigned first=option,second=5-option;delta=std::fmax(delta,6.353102*std::fabs(out.stage_rates[first]-out.stage_rates[second]));}out.low[option]=std::fmax(0.,out.rates[option]-delta);out.high[option]=out.rates[option]+delta;}
 return out;
}
void tick(){int p=active_pool();bool ok=healthy();const auto &c=settings::get();int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);
 uint64_t dt=last_observation&&now>=last_observation?uint64_t(now-last_observation)/1000:0;last_observation=now;
 for(int i=0;i<N;i++){auto &m=ps[i];if(m.observed&&m.was_enabled){if(dt>15000)m.unobserved_ms+=dt;else if(m.was_connected)m.connected_ms+=dt;else m.disconnected_ms+=dt;}m.observed=true;m.was_enabled=g_state.pools[i].enabled;m.was_connected=g_state.pools[i].connected;}
 if(ok&&p>=0){if(!healthy_since||warm_pool!=p||warm_freq!=g_state.freq_mhz||warm_mv!=g_state.core_mv||warm_cap!=c.power_cap_w){healthy_since=now;warm_pool=p;warm_freq=g_state.freq_mhz;warm_mv=g_state.core_mv;warm_cap=c.power_cap_w;}}else healthy_since=0;
 if(trial.state==1){
  if(now-trial.last_check>15000000LL)abort_trial(Abort::Controller);
  else if(!ok)abort_trial(Abort::Safety);
  else if(p!=trial.pool)abort_trial(Abort::Pool);
  else if(c.job_ms!=trial.base||c.vr_hz!=trial.vr||c.power_cap_w!=trial.cap||g_state.freq_mhz!=trial.freq||g_state.core_mv!=trial.mv)abort_trial(Abort::Config);
  else if(fabsf(g_state.chip_temp_max-trial.chip)>5||fabsf(g_state.vr_temp-trial.vr_temp)>5)abort_trial(Abort::Temperature);
  else if(!trial.measuring&&now-trial.start>=WARMUP*1000000LL){trial.measuring=true;trial.start=now;}
  else if(trial.measuring&&now-trial.start>=WINDOW*1000000LL){unsigned stage=trial.stage;trial.elapsed[stage]=(now-trial.start)/1e6;trial.rate[stage]=hunter_math::ghs(trial.work[stage],trial.elapsed[stage]);if(trial.replies[stage]<100)abort_trial(Abort::Samples);else if(stage+1==STAGES)trial.state=2;else{trial.stage++;trial.measuring=false;trial.start=now;}}
  trial.last_check=now;
 }
 // Mark unanswered submissions once, including ordinary shares. Retain entries
 // until eviction/disconnect so a late ACK can still be associated correctly.
 for(int i=0;i<N;i++)for(auto &r:ps[i].pending)if(r.valid&&!r.timed_out&&now-r.time>120000000LL){r.timed_out=true;ps[i].missed++;if(trial.state==1&&trial.pool==i)abort_trial(Abort::Replies);if(candidate_live&&last.pool==i&&last.id==r.id&&(last.state==1||last.state==2)){last.state=6;dirty=true;persisted=false;}}
 Candidate copy=last;bool save=dirty&&now>=next_save;if(save)dirty=false;portEXIT_CRITICAL(&mux);
 if(save){nvs_handle_t h;bool good=false;if(nvs_open("af_hunter",NVS_READWRITE,&h)==ESP_OK){good=nvs_set_blob(h,"candidate",&copy,sizeof(copy))==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);}portENTER_CRITICAL(&mux);persisted=good&&!dirty;if(!good){dirty=true;next_save=now+60000000LL;}else next_save=0;portEXIT_CRITICAL(&mux);}
}
void task(void*){while(true){vTaskDelay(pdMS_TO_TICKS(5000));tick();}}
}
WorkSnapshot work_snapshot(int p){WorkSnapshot out;if(!valid_pool(p))return out;int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);auto&s=ps[p];out={s.work,s.squared,(now-boot)/1e6,s.accepted,s.rejected,s.missed,s.failed};portEXIT_CRITICAL(&mux);return out;}
bool benchmark_running(){portENTER_CRITICAL(&mux);bool on=trial.state==1;portEXIT_CRITICAL(&mux);return on;}
void start(){boot=esp_timer_get_time();nvs_handle_t h;if(nvs_open("af_hunter",NVS_READONLY,&h)==ESP_OK){Candidate c;size_t n=sizeof(c);if(nvs_get_blob(h,"candidate",&c,&n)==ESP_OK&&n==sizeof(c)&&c.version==2&&c.btc<=1&&c.state<=7&&valid_pool(c.pool)){c.hash[64]=0;if(!hash_ok(c.hash))c.hash[0]=0;if(c.state==1||c.state==2)c.state=6;last=c;}nvs_close(h);}task_ok=xTaskCreate(task,"btc_hunter",4096,nullptr,2,nullptr)==pdPASS;if(!task_ok)ESP_LOGE("hunter","task start failed");}
void job_sent(int p,uint32_t gen,int64_t received,bool clean){if(!valid_pool(p)||!clean||received<=0)return;int64_t us=esp_timer_get_time()-received;if(us<0||us>60000000)return;uint32_t ms=us/1000;portENTER_CRITICAL(&mux);auto &m=ps[p];if(!m.gen_valid||m.gen!=gen){m.gen_valid=true;m.gen=gen;m.clean_ms=m.clean_n?(m.clean_ms*7+ms)/8:ms;m.clean_n++;if(ms>m.max_ms)m.max_ms=ms;}portEXIT_CRITICAL(&mux);}
void submitted(int p,uint32_t id,double diff,bool candidate,const char *hash,bool btc){if(!valid_pool(p))return;int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);auto &m=ps[p];int victim=-1;
 // A burst of low-difficulty ordinary shares must not evict a block candidate
 // awaiting its pool response. Prefer unused slots, then ordinary requests.
 for(unsigned k=0;k<PENDING;k++){unsigned j=(m.cursor+k)%PENDING;if(!m.pending[j].valid){victim=int(j);break;}}
 if(victim<0)for(unsigned k=0;k<PENDING;k++){unsigned j=(m.cursor+k)%PENDING;if(!m.pending[j].candidate){victim=int(j);break;}}
 if(victim<0){if(!candidate){m.missed++;if(trial.state==1&&trial.pool==p)abort_trial(Abort::Replies);portEXIT_CRITICAL(&mux);return;}victim=int(m.cursor%PENDING);}
 m.cursor=(unsigned(victim)+1)%PENDING;auto &r=m.pending[victim];if(r.valid){if(!r.timed_out)m.missed++;if(trial.state==1&&r.trial_id==trial.id)abort_trial(Abort::Replies);if(candidate_live&&last.pool==p&&last.id==r.id&&(last.state==1||last.state==2||last.state==6)){last.state=6;dirty=true;persisted=false;candidate_live=false;}}r=Request{};r.id=id;r.diff=std::isfinite(diff)&&diff>0&&diff<=std::ldexp(1.,224)?diff:0;r.time=now;r.valid=true;r.btc=btc;r.candidate=candidate;if(trial.state==1&&trial.pool==p){r.trial_id=trial.id;r.stage=trial.stage;r.measured=trial.measuring;}if(candidate)cand(p,id,hash,1,btc);portEXIT_CRITICAL(&mux);}
void sent(int p,uint32_t id,bool ok){if(!valid_pool(p))return;portENTER_CRITICAL(&mux);auto &m=ps[p];bool pending=false;for(auto &r:m.pending)if(r.valid&&r.id==id){pending=true;if(!ok){r.valid=false;m.failed++;if(trial.state==1&&trial.pool==p)abort_trial(Abort::Transport);}break;}
 // An ACK may arrive on the reader task before send_line returns. In that
 // case reply() already owns the outcome; do not overwrite it or count failure.
 if(pending&&candidate_live&&last.pool==p&&last.id==id&&last.state==1){last.state=ok?2:5;dirty=true;persisted=false;if(!ok)candidate_live=false;}portEXIT_CRITICAL(&mux);}
double reply(int p,uint32_t id,bool ok,bool *matched){if(matched)*matched=false;if(!valid_pool(p))return 0;double credited=0;bool candidate_reply=false;char hash[65]={};portENTER_CRITICAL(&mux);auto &m=ps[p];bool found=false;for(auto &r:m.pending)if(r.valid&&r.id==id){found=true;if(ok){m.accepted++;m.work+=r.diff;m.squared+=r.diff*r.diff;credited=r.diff;if(r.btc){m.btc_work+=r.diff;m.btc_accepted++;}}else m.rejected++;
 if(r.trial_id&&r.trial_id==trial.id&&r.stage<STAGES&&(trial.state==1||trial.state==2)){auto s=r.stage;
  if(r.measured){if(ok){trial.work[s]+=r.diff;trial.work2[s]+=r.diff*r.diff;trial.replies[s]++;if(trial.elapsed[s]>0)trial.rate[s]=hunter_math::ghs(trial.work[s],trial.elapsed[s]);}else trial.rejected[s]++;}
  else {if(ok)trial.warm_replies[s]++;else trial.warm_rejected[s]++;}
  uint32_t accepts=r.measured?trial.replies[s]:trial.warm_replies[s],rejects=r.measured?trial.rejected[s]:trial.warm_rejected[s];if(trial.state==1&&accepts+rejects>=25&&double(rejects)/(accepts+rejects)>.01)abort_trial(Abort::Replies);
 }
 candidate_reply=r.candidate;r.valid=false;break;}if(found&&candidate_live&&last.pool==p&&last.id==id&&(last.state==1||last.state==2||last.state==6)){last.state=ok?3:4;dirty=true;persisted=false;candidate_live=false;memcpy(hash,last.hash,sizeof(hash));}portEXIT_CRITICAL(&mux);if(matched)*matched=found;if(candidate_reply){ESP_LOGW("hunter","candidate id %lu %s: %s by pool %d",(unsigned long)id,hash,ok?"accepted":"rejected",p+1);notify::post(NOTIFY_BLOCK,"BLOCK CANDIDATE id %lu %s by pool %d: %s (not chain confirmation)",(unsigned long)id,ok?"accepted":"rejected",p+1,hash);}return credited;}
void disconnected(int p){if(!valid_pool(p))return;portENTER_CRITICAL(&mux);if(warm_pool==p){healthy_since=0;warm_pool=-1;}for(auto &r:ps[p].pending)if(r.valid){r.valid=false;if(!r.timed_out)ps[p].missed++;}if(candidate_live&&last.pool==p&&(last.state==1||last.state==2||last.state==6)){last.state=6;dirty=true;persisted=false;candidate_live=false;}if(trial.state==1&&trial.pool==p)abort_trial(Abort::Pool);portEXIT_CRITICAL(&mux);}
void sv2_candidate(int p,const char *hash,bool ok,bool btc){if(!valid_pool(p))return;portENTER_CRITICAL(&mux);cand(p,0,hash,ok?7:5,btc);portEXIT_CRITICAL(&mux);}
void unavailable_candidate(int p,const char *hash,bool btc){if(!valid_pool(p))return;portENTER_CRITICAL(&mux);cand(p,0,hash,5,btc);portEXIT_CRITICAL(&mux);}
bool candidate_snapshot(char hash[65],int &pool){if(!hash)return false;portENTER_CRITICAL(&mux);bool valid=last.state&&last.btc&&valid_pool(last.pool)&&hash_ok(last.hash);if(valid){memcpy(hash,last.hash,65);pool=last.pool;}else{hash[0]=0;pool=-1;}portEXIT_CRITICAL(&mux);return valid;}
uint16_t interval(uint16_t configured){int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);if(trial.state==1){if(configured!=trial.base)abort_trial(Abort::Config);else if(now-trial.last_check>15000000LL)abort_trial(Abort::Controller);}uint16_t out=trial.state==1?steps[order[trial.stage]]:configured;portEXIT_CRITICAL(&mux);return out;}
namespace {
bool append_json(char *buf,size_t capacity,size_t &used,const char *format,...) __attribute__((format(printf,4,5)));
bool append_json(char *buf,size_t capacity,size_t &used,const char *format,...){if(used>=capacity)return false;va_list args;va_start(args,format);int written=vsnprintf(buf+used,capacity-used,format,args);va_end(args);if(written<0||size_t(written)>=capacity-used)return false;used+=size_t(written);return true;}
}
esp_err_t get(httpd_req_t *req){
 struct Row{double work,btc;uint32_t ba,a,r,miss,failed,n,ms,max;uint64_t connected,disconnected,unobserved;};Row rows[N];Candidate c;Trial t;bool saved;int64_t now=esp_timer_get_time();
 portENTER_CRITICAL(&mux);for(int i=0;i<N;i++){auto &m=ps[i];rows[i]={m.work,m.btc_work,m.btc_accepted,m.accepted,m.rejected,m.missed,m.failed,m.clean_n,m.clean_ms,m.max_ms,m.connected_ms,m.disconnected_ms,m.unobserved_ms};}c=last;t=trial;saved=persisted;portEXIT_CRITICAL(&mux);
 // Keep the web-server stack bounded and reject overflow rather than emitting
 // partial JSON or passing an underflowed length to snprintf.
 constexpr size_t capacity=4096;char *buf=(char*)malloc(capacity);if(!buf)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"no memory");size_t n=0;
 bool good=append_json(buf,capacity,n,"{\"native\":true,\"taskOk\":%s,\"seconds\":%.0f,\"samplingSeconds\":5,\"pools\":[",task_ok?"true":"false",(now-boot)/1e6);
 for(int i=0;good&&i<N;i++){auto &r=rows[i];good=append_json(buf,capacity,n,"%s{\"work\":%.8g,\"btcWork\":%.8g,\"btcAccepted\":%lu,\"accepted\":%lu,\"rejected\":%lu,\"missing\":%lu,\"failed\":%lu,\"cleanN\":%lu,\"cleanMs\":%lu,\"cleanMax\":%lu,\"connectedSeconds\":%llu,\"disconnectedSeconds\":%llu,\"observedSeconds\":%llu,\"unobservedSeconds\":%llu}",i?",":"",r.work,r.btc,(unsigned long)r.ba,(unsigned long)r.a,(unsigned long)r.r,(unsigned long)r.miss,(unsigned long)r.failed,(unsigned long)r.n,(unsigned long)r.ms,(unsigned long)r.max,(unsigned long long)(r.connected/1000),(unsigned long long)(r.disconnected/1000),(unsigned long long)((r.connected+r.disconnected)/1000),(unsigned long long)(r.unobserved/1000));}
 auto summary=summarize_trial(t,now);auto &low=summary.low;auto &high=summary.high;auto &rates=summary.rates;auto &accepted=summary.accepted;auto &rejected=summary.rejected;auto &repeats=summary.repeats;auto &stage_rates=summary.stage_rates;
 const char *phase=t.state==1?(t.measuring?"measure":"warmup"):t.state==2?"done":t.state==3?"aborted":"idle";
 good=good&&append_json(buf,capacity,n,"],\"candidate\":{\"state\":%u,\"pool\":%d,\"hash\":\"%s\",\"persisted\":%s},\"trial\":{\"state\":%u,\"stage\":%u,\"phase\":\"%s\",\"intervalMs\":%u,\"totalStages\":6,\"round\":%u,\"warmupSeconds\":%u,\"measurementSeconds\":%u,\"abortReason\":\"%s\",\"elapsed\":%.0f,\"uncertain\":true,\"autoApply\":false,\"confidenceMethod\":\"weighted_poisson_and_two_repeat_spread\",\"rates\":[%.3f,%.3f,%.3f],\"ci95Low\":[%.3f,%.3f,%.3f],\"ci95High\":[%.3f,%.3f,%.3f],\"accepted\":[%lu,%lu,%lu],\"rejected\":[%lu,%lu,%lu],\"repeatsCompleted\":[%u,%u,%u],\"stageRates\":[",unsigned(c.state),c.pool,c.hash,saved?"true":"false",unsigned(t.state),unsigned(t.stage),phase,unsigned(steps[order[t.stage]]),unsigned(t.stage/3+1),unsigned(WARMUP),unsigned(WINDOW),abort_name(t.reason),t.state==1?(now-t.start)/1e6:0,rates[0],rates[1],rates[2],low[0],low[1],low[2],high[0],high[1],high[2],(unsigned long)accepted[0],(unsigned long)accepted[1],(unsigned long)accepted[2],(unsigned long)rejected[0],(unsigned long)rejected[1],(unsigned long)rejected[2],repeats[0],repeats[1],repeats[2]);
 for(unsigned stage=0;good&&stage<STAGES;stage++)good=append_json(buf,capacity,n,"%s%.3f",stage?",":"",stage_rates[stage]);
 good=good&&append_json(buf,capacity,n,"],\"stageAccepted\":[");for(unsigned stage=0;good&&stage<STAGES;stage++)good=append_json(buf,capacity,n,"%s%lu",stage?",":"",(unsigned long)t.replies[stage]);
 good=good&&append_json(buf,capacity,n,"],\"stageRejected\":[");for(unsigned stage=0;good&&stage<STAGES;stage++)good=append_json(buf,capacity,n,"%s%lu",stage?",":"",(unsigned long)t.rejected[stage]);good=good&&append_json(buf,capacity,n,"]}}");
 if(!good){free(buf);return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"response too large");}httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");auto result=httpd_resp_sendstr(req,buf);free(buf);return result;
}
esp_err_t set(httpd_req_t *req){char body[128];if(req->content_len<=0||(size_t)req->content_len>=sizeof(body))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"bad body");int got=0;while(got<(int)req->content_len){int n=httpd_req_recv(req,body+got,req->content_len-got);if(n<=0)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"incomplete");got+=n;}body[got]=0;cJSON *j=json_parse(body);if(!j)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"bad json");auto *s=cJSON_GetObjectItem(j,"start");bool valid=cJSON_IsBool(s),go=cJSON_IsTrue(s);cJSON_Delete(j);if(!valid)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"start bool required");int p=active_pool();auto &cfg=settings::get();bool ok=task_ok&&healthy()&&p>=0&&g_state.pools[p].proto<=1&&cfg.vr_hz==0&&(!cfg.job_ms||cfg.job_ms==500);int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);if(go&&(!healthy_since||now-healthy_since<WINDOW*1000000LL))ok=false;if(!go){abort_trial(Abort::User);}else if(ok&&trial.state!=1){trial=Trial{};if(++trial_sequence==0)++trial_sequence;trial.id=trial_sequence;trial.state=1;trial.pool=p;trial.chip=g_state.chip_temp_max;trial.vr_temp=g_state.vr_temp;trial.freq=g_state.freq_mhz;trial.mv=g_state.core_mv;trial.base=cfg.job_ms;trial.vr=cfg.vr_hz;trial.cap=cfg.power_cap_w;trial.start=trial.last_check=now;}else ok=false;portEXIT_CRITICAL(&mux);if(go&&!ok)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Need 30 min stable capped auto-tune, one V1 pool, default timing, no running test");return httpd_resp_sendstr(req,"OK");}
}
