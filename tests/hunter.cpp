#include <cassert>
#include <string>
#include <vector>
#include <cstring>
#include <cmath>
#include <iostream>
#include "../overlay/main/core/hunter.cpp"
MinerState g_state{};static Settings cfg{};namespace settings{Settings&get(){return cfg;}}
static int64_t clock_us=1000000;int64_t esp_timer_get_time(){return clock_us;}
void vTaskDelay(unsigned){}int xTaskCreate(void(*)(void*),const char*,unsigned,void*,int,void*){return pdPASS;}
static bool nvs_fail=false;static unsigned nvs_writes=0;static std::vector<unsigned char> stored;int nvs_open(const char*,int,nvs_handle_t*h){*h=1;return ESP_OK;}int nvs_get_blob(nvs_handle_t,const char*,void*p,size_t*n){if(stored.size()!=*n)return ESP_FAIL;memcpy(p,stored.data(),*n);return ESP_OK;}int nvs_set_blob(nvs_handle_t,const char*,const void*p,size_t n){++nvs_writes;if(nvs_fail)return ESP_FAIL;auto*q=(const unsigned char*)p;stored.assign(q,q+n);return ESP_OK;}int nvs_commit(nvs_handle_t){return ESP_OK;}void nvs_close(nvs_handle_t){}
static int notifications=0;namespace notify{void post(int,const char*,...){++notifications;}}
static std::string body,out;static cJSON obj{},val{};static bool valid_json=false;static unsigned parse_calls=0;
cJSON*cJSON_Parse(const char*s){++parse_calls;body=s;valid_json=body=="{\"start\":true}"||body=="{\"start\":false}";val.valueint=body=="{\"start\":true}";return &obj;}
cJSON*cJSON_GetObjectItem(cJSON*,const char*){return valid_json?&val:nullptr;}bool cJSON_IsBool(cJSON*p){return p==&val;}bool cJSON_IsTrue(cJSON*p){return p&&p->valueint==1;}void cJSON_Delete(cJSON*){}
int httpd_resp_send_err(httpd_req_t*,int code,const char*s){out=s;return code;}int httpd_resp_sendstr(httpd_req_t*,const char*s){out=s;return 0;}int httpd_resp_set_type(httpd_req_t*,const char*){return 0;}int httpd_resp_set_hdr(httpd_req_t*,const char*,const char*){return 0;}int httpd_req_recv(httpd_req_t*,char*p,size_t n){memcpy(p,body.data(),n);return (int)n;}
static void command(bool start,int want=0){body=start?"{\"start\":true}":"{\"start\":false}";httpd_req_t req{(int)body.size()};auto rc=hunter::set(&req);if(rc!=want)std::cerr<<"command start="<<start<<" rc="<<rc<<" expected="<<want<<" now="<<clock_us<<" since="<<hunter::healthy_since<<" state="<<unsigned(hunter::trial.state)<<" msg="<<out<<"\n";assert(rc==want);}
static void advance(unsigned sec){while(sec){unsigned step=sec<5?sec:5;clock_us+=(int64_t)step*1000000;sec-=step;g_state.telemetry_ms=g_state.hash_counter_ms=uint32_t(clock_us/1000);hunter::tick();}}
static void track(int p,uint32_t id,double difficulty,bool candidate,const char *hash){hunter::submitted(p,id,difficulty,candidate,hash,true);}
static void unavailable(int p,const char *hash){hunter::unavailable_candidate(p,hash,true);}
static void shares(unsigned base,unsigned count,double diff){for(unsigned i=0;i<count;i++){track(0,base+i,diff,false,nullptr);hunter::sent(0,base+i,true);assert(hunter::reply(0,base+i,true)==diff);}}
int main(){using namespace hunter_math;uint8_t t[32];assert(target(0x1d00ffff,t)&&t[26]==0xff&&t[27]==0xff&&t[28]==0);assert(meets(t,0x1d00ffff));t[0]++;assert(!meets(t,0x1d00ffff));t[0]=0;t[26]--;assert(meets(t,0x1d00ffff));assert(!target(0x1d80ffff,t));assert(!target(0x23000001,t));assert(!target(0x01000001,t));assert(!target(0,t));assert(target(0x220000ff,t)&&t[31]==0xff);assert(!target(0x22000100,t));assert(target(0x2100ffff,t)&&t[31]==0xff);assert(en2_capacity(1)==256&&en2_capacity(3)==16777216&&en2_capacity(4)==4294967296ULL&&en2_capacity(16)==4294967296ULL);assert(en2_value(0x100,1)==0&&en2_value(0x123456,2)==0x3456&&en2_value(0xffffffffu,16)==0xffffffffu);assert(!rate_ok(3933240));assert(rate_ok(1550));assert(!rate_ok(NAN));assert(std::abs(chance(1550,148364561003867.41,31536000)-0.0000767)<0.000001);
 // Genesis block's SHA256d in internal byte order.
 const char*gen="6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000";uint8_t h[32];for(int i=0;i<32;i++){unsigned x;sscanf(gen+2*i,"%2x",&x);h[i]=x;}assert(meets(h,0x1d00ffff));
 assert(btc_target_ok(0x1d00ffff)&&btc_target_ok(0x1c7fffff));assert(!btc_target_ok(0x1d010000)&&!btc_target_ok(0x207fffff)&&!meets_btc(h,0x207fffff));assert(meets_btc(h,0x1d00ffff));
 hunter::start();g_state.telemetry_ms=g_state.hash_counter_ms=uint32_t(clock_us/1000);g_state.status=SysStatus::Mining;g_state.temp_ok=g_state.vr_temp_ok=g_state.pool_connected=g_state.fan_present[0]=true;g_state.fan_rpm[0]=5000;g_state.tuner.phase=TunerPhase::Locked;g_state.chip_temp_max=55;g_state.vr_temp=64;g_state.vin=5.1;g_state.pin=23;g_state.hashrate_ghs=1550;g_state.expected_ghs=1600;g_state.error_pct=.3;g_state.freq_mhz=786;g_state.core_mv=1170;g_state.pools[0].enabled=g_state.pools[0].connected=true;g_state.pools[0].work_pct=100;strcpy(g_state.pools[0].host,"stratum.bitaxe.de");cfg.autotune=true;cfg.tune_goal=1;cfg.power_cap_w=25;cfg.pool_mode=PoolMode::Failover;
 track(0,100,1337,false,nullptr);hunter::sent(0,100,true);assert(hunter::reply(0,100,true)==1337);assert(hunter::reply(0,100,true)==0);assert(hunter::ps[0].accepted==1&&hunter::ps[0].work==1337&&hunter::ps[0].btc_work==1337);
 bool matched=true;assert(hunter::reply(0,99999,false,&matched)==0&&!matched);auto rejected_before=hunter::ps[0].rejected;
 track(0,990,42,false,nullptr);assert(hunter::reply(0,990,false,&matched)==0&&matched);assert(hunter::reply(0,990,false,&matched)==0&&!matched);assert(hunter::ps[0].rejected==rejected_before+1);
 track(0,991,43,false,nullptr);assert(hunter::reply(1,991,true,&matched)==0&&!matched);assert(hunter::reply(0,991,true,&matched)==43&&matched);
 track(0,992,NAN,false,nullptr);assert(hunter::reply(0,992,true,&matched)==0&&matched);track(0,993,1e300,false,nullptr);assert(hunter::reply(0,993,true,&matched)==0&&matched);
 track(0,101,1000,true,gen);hunter::sent(0,101,true);assert(hunter::last.state==2);assert(hunter::reply(0,101,true)==1000);assert(hunter::last.state==3&&notifications==1);advance(5);assert(!stored.empty());
 // Reader can ACK before send() returns, including partial-write failure.
 auto failures=hunter::ps[0].failed;track(0,994,10,true,gen);assert(hunter::reply(0,994,true,&matched)==10&&matched);hunter::sent(0,994,false);assert(hunter::last.state==3&&hunter::ps[0].failed==failures);assert(hunter::reply(0,994,true,&matched)==0&&!matched);
 track(0,995,10,true,gen);hunter::sent(0,995,true);advance(121);assert(hunter::last.state==6);auto lost=hunter::ps[0].missed;advance(121);assert(hunter::ps[0].missed==lost);assert(hunter::reply(0,995,true,&matched)==10&&matched&&hunter::last.state==3);
 track(0,996,50,true,gen);hunter::sent(0,996,true);for(unsigned i=0;i<200;i++)track(0,10000+i,1,false,nullptr);assert(hunter::reply(0,996,true,&matched)==50&&matched&&hunter::last.state==3);hunter::disconnected(0);
 track(0,102,2000,true,gen);hunter::sent(0,102,true);advance(121);assert(hunter::last.state==6);hunter::disconnected(0);assert(hunter::reply(0,102,true)==0&&hunter::last.state==6);
 track(0,103,2000,true,gen);hunter::sent(0,103,false);assert(hunter::last.state==5&&hunter::ps[0].failed==1);hunter::sv2_candidate(1,gen,true,true);assert(hunter::last.state==7);
 hunter::job_sent(0,1,clock_us-100000,true);hunter::job_sent(0,1,clock_us-200000,true);assert(hunter::ps[0].clean_n==1&&hunter::ps[0].clean_ms==100);hunter::job_sent(0,2,clock_us-200000,true);assert(hunter::ps[0].clean_n==2&&hunter::ps[0].max_ms==200);
 // Failed persistence is visible and retries no more than once per minute.
 nvs_fail=true;unavailable(0,gen);advance(5);assert(!hunter::persisted&&hunter::dirty);auto writes=nvs_writes;advance(5);assert(nvs_writes==writes);nvs_fail=false;advance(60);assert(hunter::persisted&&!hunter::dirty);
 // Candidate hashes read back from flash/API cannot inject JSON.
 unavailable(0,"\"bad");httpd_req_t safe_req{};assert(hunter::get(&safe_req)==0&&out.find("bad")==std::string::npos);
 command(true,400);advance(5);advance(1800);track(0,9000,100,false,nullptr);command(true);assert(hunter::reply(0,9000,true)==100&&hunter::trial.replies[0]==0);assert(hunter::interval(0)==500&&!hunter::trial.measuring);
 // Balanced two-round trial: warmups never contribute accepted work.
 for(unsigned stage=0;stage<6;stage++){
  assert(hunter::trial.stage==stage&&!hunter::trial.measuring&&hunter::interval(0)==hunter::steps[hunter::order[stage]]);
  shares(50000+stage*1000,50,1337);assert(hunter::trial.replies[stage]==0);advance(300);assert(hunter::trial.measuring);
  shares(60000+stage*1000,500+stage*10,1337);advance(1795);track(0,9001+stage,100,false,nullptr);advance(5);
  assert(hunter::reply(0,9001+stage,true)==100&&hunter::trial.replies[stage]==501+stage*10);
 }
 assert(hunter::trial.state==2&&hunter::interval(0)==0&&hunter::trial.replies[5]==551&&cfg.job_ms==0&&cfg.power_cap_w==25);
 auto summary=hunter::summarize_trial(hunter::trial,clock_us);for(unsigned option=0;option<3;option++){assert(summary.repeats[option]==2&&summary.accepted[option]==1052);assert(summary.low[option]<=summary.rates[option]&&summary.high[option]>=summary.rates[option]);auto spread=6.353102*std::abs(summary.stage_rates[option]-summary.stage_rates[5-option]);assert(summary.high[option]-summary.rates[option]>=spread*.999999);}
 httpd_req_t completed_req{};assert(hunter::get(&completed_req)==0&&out.find("\"repeatsCompleted\":[2,2,2]")!=std::string::npos&&out.find("\"phase\":\"done\"")!=std::string::npos&&out.find("\"autoApply\":false")!=std::string::npos);
 // Continuous warmup must be lost on even a brief connection interruption.
 hunter::disconnected(0);command(true,400);advance(1805);
 // Insufficient sampling and transport loss stop the benchmark and restore timing.
 command(true);advance(300);advance(1800);assert(hunter::trial.state==3&&hunter::trial.reason==hunter::Abort::Samples&&hunter::interval(0)==0);
 command(true);advance(300);track(0,9200,10,false,nullptr);hunter::sent(0,9200,false);assert(hunter::trial.state==3&&hunter::trial.reason==hunter::Abort::Transport&&hunter::interval(0)==0);
 // A valid discovered BTC candidate is readable without any resubmission.
 unavailable(0,gen);char snapshot[65];int snapshot_pool=-1;assert(hunter::candidate_snapshot(snapshot,snapshot_pool)&&!strcmp(snapshot,gen)&&snapshot_pool==0);unavailable(0,"bad");assert(!hunter::candidate_snapshot(snapshot,snapshot_pool));
 command(true);g_state.vr_temp=80;advance(5);assert(hunter::trial.state==3&&hunter::interval(0)==0);command(true,400);g_state.vr_temp=64;advance(5);advance(1800);command(true);assert(hunter::interval(600)==600&&hunter::trial.state==3);
 command(true);clock_us+=16000000;assert(hunter::interval(0)==0&&hunter::trial.state==3);g_state.telemetry_ms=g_state.hash_counter_ms=uint32_t(clock_us/1000);command(true);command(false);assert(hunter::interval(0)==0);httpd_req_t req{};assert(hunter::get(&req)==0);assert(out.find("\"btcWork\"")!=std::string::npos&&out.find("\"taskOk\":true")!=std::string::npos);
 // Per-slot availability is sampled, and a stalled observer is marked unknown.
 hunter::tick();auto connected=hunter::ps[0].connected_ms;g_state.pools[0].connected=false;advance(5);advance(10);assert(hunter::ps[0].connected_ms==connected+5000&&hunter::ps[0].disconnected_ms>=10000);auto unseen=hunter::ps[0].unobserved_ms;clock_us+=20000000;g_state.telemetry_ms=g_state.hash_counter_ms=uint32_t(clock_us/1000);hunter::tick();assert(hunter::ps[0].unobserved_ms==unseen+20000);g_state.pools[0].connected=true;advance(5);assert(hunter::get(&req)==0);
 // Depth guard must reject before invoking the recursive JSON parser.
 auto parsed=parse_calls;body=std::string(20,'[')+std::string(20,']');httpd_req_t nested{int(body.size())};assert(hunter::set(&nested)==400&&parse_calls==parsed);assert(hunter::get(&req)==0);
 if(getenv("AXEFORGE_API_JSON"))std::cout<<"API_JSON "<<out<<"\n";
 std::cout<<"PASS: compact BTC pow limit, unknown/rejected duplicate ACK, ACK-before-send, late ACK, throttled NVS retry, exact trial-stage attribution, exact compact target/genesis, outlier, probability, V1 difficulty ledger/duplicate replies, candidate ack/timeout/failed/SV2, flash mock, generation lag, six balanced timed stages with excluded warmup, repeated confidence, abort/restore, candidate snapshot, sampled pool connectivity, API\n";
}
