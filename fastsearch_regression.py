#!/usr/bin/env python3
"""Install regressions that compile the actual final controller and tuner phase."""
from pathlib import Path
import sys
root = Path(sys.argv[1]).resolve()

def change(s, old, new):
    assert s.count(old) == 1, (old[:100], s.count(old))
    return s.replace(old, new, 1)

p = root / 'tests/stubs/nvs.h'
s = p.read_text()
s += '\nconstexpr int ESP_ERR_NVS_NOT_FOUND=0x1102;\n'
p.write_text(s)
p = root / 'tests/turbo.cpp'
s = p.read_text()
s = change(s, '#include \"../overlay/main/core/turbo.cpp\"', '#include \"esp_err.h\"\n#include \"../overlay/main/core/turbo.cpp\"')
s = change(s, 'bench=false,write_fail=false;', 'bench=false,write_fail=false,commit_fail=false,open_fail=false,read_fail=false;')
s = change(s, '*h=1;return ESP_OK;}int nvs_get_blob', 'if(open_fail)return ESP_FAIL;*h=1;return ESP_OK;}int nvs_get_blob')
s = change(s, 'auto&v=saved[k];if(*n!=v.size())return ESP_FAIL;', 'if(read_fail)return ESP_FAIL;if(!saved.count(k))return ESP_ERR_NVS_NOT_FOUND;auto&v=saved[k];if(*n!=v.size())return ESP_FAIL;')
s = change(s, 'std::vector<unsigned char>>saved;', 'std::vector<unsigned char>>saved,pending;')
s = change(s, 'saved[k]={a,a+n};return ESP_OK;}int nvs_commit(nvs_handle_t){return write_fail?ESP_FAIL:ESP_OK;}void nvs_close(nvs_handle_t){}', 'pending[k]={a,a+n};return ESP_OK;}int nvs_commit(nvs_handle_t){if(write_fail||commit_fail)return ESP_FAIL;for(auto&v:pending)saved[v.first]=v.second;pending.clear();return ESP_OK;}void nvs_close(nvs_handle_t){pending.clear();}')
s = change(s, 'bench=write_fail=false;', 'bench=write_fail=commit_fail=open_fail=read_fail=false;')
s = change(s, 'g_state.pin=30.1;assert(turbo::monitor_trip()==turbo::Reason::Power);', 'g_state.pin=30.1;assert(turbo::monitor_trip()==turbo::Reason::None);assert(turbo::monitor_trip()==turbo::Reason::HardwarePower);')
s = change(s, 'free_nvs=128;assert(!turbo::remember(825,1170,1650,24)&&turbo::reason()==turbo::Reason::Storage);', 'free_nvs=128;assert(turbo::remember(825,1170,1650,24)&&turbo::persisted);')
s = change(s, 'turbo::psu_watts=15;assert(turbo::monitor_trip()==turbo::Reason::Power);', 'turbo::psu_watts=15;assert(turbo::monitor_trip()==turbo::Reason::None);assert(turbo::monitor_trip()==turbo::Reason::HardwarePower);')
s = change(s, ' reset();cfg.overclock=false;', r'''
 // The old point's error counter may settle for two seconds after recovery,
 // but neither persistent errors nor invalid counters may bypass ASIC guards.
 reset();begin();g_state.error_pct=4.1f;
 assert(!turbo::check()&&turbo::reason()==turbo::Reason::Errors);
 assert(turbo::recovery_ready());turbo::resume();assert(turbo::check());
 now_us+=3000000;fresh();
 assert(!turbo::check()&&turbo::reason()==turbo::Reason::Errors);
 reset();begin();g_state.error_pct=NAN;assert(!turbo::check());
 reset();begin();g_state.error_pct=4.1f;turbo::stop(turbo::Reason::Errors);
 turbo::resume();g_state.pool_connected=false;
 assert(!turbo::check()&&turbo::reason()==turbo::Reason::Network);
 reset();begin();g_state.error_pct=4.1f;turbo::stop(turbo::Reason::Errors);
 turbo::resume();cfg.chip_tune=true;
 assert(!turbo::check()&&turbo::reason()==turbo::Reason::Settings);

 // A low user request is a software search ceiling, never an absolute
 // hardware power rating. The watchdog must not convert it into a fault.
 reset();begin();turbo::sync_cap(18);g_state.pin=18.1f;
 assert(turbo::monitor_trip()==turbo::Reason::None);
 assert(turbo::check());assert(!turbo::check()&&turbo::reason()==turbo::Reason::Power);
 assert(turbo::recovery_ready());
 reset();begin();g_state.pin=30.1f;
 assert(!turbo::check()&&turbo::reason()==turbo::Reason::HardwarePower);
 assert(!turbo::recovery_ready());

 // Ordinary effective-budget crossing remains recoverable; an absolute PSU
 // crossing is latched fatal and cannot be turned into HOLD by recovery.
 reset();begin();turbo::archive=turbo::Archive{};
 turbo::probe(838,1210,1670.967f,25.223f,55,60);
 turbo::probe(850,1220,1624.637f,24.589f,55,60);
 turbo::probe(863,1230,1700.996f,25.512f,55,60);
 turbo::probe(825,1200,1600,24,55,60);
 g_state.freq_mhz=863;g_state.core_mv=1230;g_state.pin=25.512f;assert(turbo::check());assert(!turbo::check());
 assert(turbo::reason()==turbo::Reason::Power&&turbo::recovery_ready());
 turbo::Point candidate;
 assert(turbo::next_candidate(candidate)&&candidate.mhz==850);
 assert(turbo::next_candidate(candidate)&&candidate.mhz==825);
 assert(!turbo::next_candidate(candidate)); // each pair only once, 863 never safe
 turbo::disarm(turbo::Reason::HardwarePower);
 assert(!turbo::recovery_ready());turbo::holding(turbo::Reason::Power);
 assert(turbo::cancelled()&&turbo::reason()==turbo::Reason::HardwarePower);

 // Rank performance rather than recency; stale and changed-environment points
 // cannot become winners solely because they once measured well.
 reset();begin();turbo::archive=turbo::Archive{};
 assert(turbo::remember(850,1220,1670,24.6f,55,60));
 assert(turbo::remember(825,1200,1600,24,55,60));
 g_state.core_mv=1300;assert(turbo::next_candidate(candidate)&&candidate.mhz==850);
 assert(turbo::next_candidate(candidate)&&candidate.mhz==825);
 assert(!turbo::next_candidate(candidate));
 reset();begin();g_state.core_mv=1300;turbo::archive.points[0].time=uint32_t(time(nullptr)-90000);
 turbo::archive.points[1].time=uint32_t(time(nullptr)+60);
 assert(!turbo::next_candidate(candidate));
 reset();begin();turbo::archive=turbo::Archive{};
 assert(turbo::remember(850,1220,1670,24.6f,45,50));
 g_state.core_mv=1300;assert(!turbo::next_candidate(candidate)); // environment is now 10 C hotter

 // Flash set/commit failures retain RAM measurement and truthfully report
 // persisted=false; a failed commit must not replace the last durable map.
 reset();begin();turbo::archive=turbo::Archive{};
 assert(turbo::remember(800,1170,1600,23.5f,55,60));
 const auto durable=saved["map_v4"];
 write_fail=true;assert(turbo::remember(825,1200,1650,24,55,60));
 assert(!turbo::persisted&&turbo::storage_error!=ESP_OK&&!turbo::cancelled());
 assert(saved["map_v4"]==durable);
 write_fail=false;commit_fail=true;
 assert(turbo::remember(850,1220,1670,24.6f,55,60));
 assert(!turbo::persisted&&turbo::storage_error!=ESP_OK&&saved["map_v4"]==durable);
 commit_fail=false;
 turbo::finish();turbo::archive=turbo::Archive{};
 turbo::start();assert(!turbo::engaged());begin();
 assert(turbo::next_candidate(candidate)&&candidate.mhz==800);
 assert(!turbo::next_candidate(candidate)); // failed records did not survive reboot
 turbo::finish();open_fail=true;turbo::start();
 assert(!turbo::persisted&&turbo::storage_error!=ESP_OK&&!cfg.overclock);
 open_fail=false;reset();read_fail=true;turbo::start();
 assert(!turbo::persisted&&turbo::storage_error!=ESP_OK&&!cfg.overclock);
 read_fail=false;reset();assert(saved.count("map_v4")&&!saved.at("map_v4").empty());saved.at("map_v4")[0]^=1;turbo::start();
 assert(!turbo::persisted&&turbo::storage_error!=ESP_OK);
 saved["map_v4"]=durable;reset();turbo::start();assert(turbo::persisted&&turbo::storage_error==ESP_OK);
 // Repeated failed writes and commits must never replace the durable map.
 // Exercise the actual controller under alternating flash faults, then reboot.
 reset();begin();turbo::archive=turbo::Archive{};
 assert(turbo::remember(800,1170,1600,23.5f,55,60));
 const auto baseline=saved.at("map_v4");
 for(unsigned cycle=0;cycle<256;cycle++){
  write_fail=(cycle%2)==0;commit_fail=!write_fail;
  assert(turbo::remember(825,1200,1650,24,55,60));
  assert(!turbo::persisted&&turbo::storage_error!=ESP_OK);
  assert(saved.at("map_v4")==baseline&&pending.empty());
 }
 write_fail=commit_fail=false;
 turbo::finish();turbo::archive=turbo::Archive{};turbo::start();
 assert(turbo::persisted&&turbo::storage_error==ESP_OK);
 begin();assert(turbo::next_candidate(candidate)&&candidate.mhz==800);
 assert(!turbo::next_candidate(candidate));turbo::finish();


 // The API reports the complete attempt count while preserving a bounded,
 // chronological ring for the browser even beyond sixteen attempts.
 reset();begin();
 for(unsigned i=0;i<20;i++)turbo::trial(uint16_t(600+i),1170,float(1200+i),23,0);
 httpd_req_t history_req{};assert(turbo::get(&history_req)==0);
 auto*history=cJSON_Parse(response.c_str());assert(history);
 assert(cJSON_GetObjectItem(history,"totalSteps")->valueint==20);
 auto*trials=cJSON_GetObjectItem(history,"trials");assert(cJSON_GetArraySize(trials)==16);
 assert(cJSON_GetArrayItem(cJSON_GetArrayItem(trials,0),0)->valueint==604);
 assert(cJSON_GetArrayItem(cJSON_GetArrayItem(trials,15),0)->valueint==619);
 assert(cJSON_GetObjectItem(history,"storageError"));cJSON_Delete(history);
 turbo::finish();
 reset();cfg.overclock=false;''')
p.write_text(s)
print('Installed actual-controller power/candidate/NVS/reboot/history regressions')

p = root / 'tests/turbo_phase.py'
s = p.read_text()
a = s.index('namespace turbo{')
b = s.index('static uint16_t held(', a)
s = s[:a] + r'''
namespace turbo{
bool unlocked(){return true;}bool better(float,uint16_t){return true;}
static bool on=true,stop_flag=false,queued=true,fatal=false;
static Reason why=Reason::None;static Point anchor;
static std::vector<Point> candidates;static std::vector<unsigned> selected;
bool active(){return on;}bool cancelled(){return stop_flag||fatal;}bool pending(){return queued;}
uint16_t max_frequency(){return 1000;}float power_budget(){return 25;}
bool headroom(float peak){return peak>0&&peak<=24.5f;}
bool check(){return !cancelled();}void changing(){}Reason reason(){return why;}
void stop(Reason r){why=r;stop_flag=true;if(r!=Reason::Power&&r!=Reason::Errors)fatal=true;}
bool begin(Point&a){queued=false;on=true;stop_flag=fatal=false;why=Reason::None;a=anchor={786,1170,23,1550,1500,1790000000,30,100};return true;}
Point start_point(){return anchor;}
void probe(uint16_t f,uint16_t mv,float gh,float w,float chip,float vr){candidates.push_back({f,mv,w,gh,0,1790000000,30,0,chip,vr,5.1f});}
// A deterministic fake supplies measured candidates; actual ranking, admissibility
// and duplicate suppression are independently tested by tests/turbo.cpp.
bool next_candidate(Point&p,uint16_t below){while(!candidates.empty()){p=candidates.back();candidates.pop_back();if(p.mhz<below&&headroom(p.watts))return true;}return false;}
bool recovery_ready(){return !fatal;}
void resume(){if(!fatal){stop_flag=false;why=Reason::None;}}
bool remember(uint16_t,uint16_t,float,float,float,float){return true;}
void verified(uint16_t f,uint16_t,float,float){selected.push_back(f);}
void holding(Reason r){if(!fatal){why=r;stop_flag=false;}}
void finish(){on=false;queued=false;stop_flag=false;}
Point fallback(uint16_t,float){return anchor;}
}
''' + s[b:]
s = change(s, 'enum class Scenario{Frequency,Power,Errors,Pll,Voltage,NeedVoltage};', 'enum class Scenario{Frequency,Power,Errors,Pll,Voltage,NeedVoltage,SoftPower,HardwarePower,BestUnstable,AllUnstable,HoldDrift};')
a = s.index('static std::vector<unsigned> probe_f,probe_mv;')
b = s.index("\n'''+apply+climb+phase", a)
s = s[:a] + r'''
static std::vector<unsigned> probe_f,probe_mv,hold_f;
static std::vector<int> probe_windows;
static unsigned hold_samples=0;
static Result measure(int,int window,float,float){
 probe_f.push_back(f);probe_mv.push_back(mv);probe_windows.push_back(window);
 Result r{Verdict::Stable,float(f*2),0,0,55,60,22,22,20};
 if(g_state.tuner.phase==TunerPhase::Locked){
  hold_f.push_back(f);++hold_samples;
  if(scenario==Scenario::HoldDrift&&hold_samples==2){turbo::stop(turbo::Reason::Power);r.verdict=Verdict::Aborted;return r;}
  if(hold_samples<=4)return r;
  turbo::stop(turbo::Reason::User);r.verdict=Verdict::Aborted;return r;
 }
 if(window==FAST_WINDOW_S&&f>=863&&(scenario==Scenario::SoftPower||scenario==Scenario::BestUnstable||scenario==Scenario::AllUnstable||scenario==Scenario::HardwarePower||scenario==Scenario::HoldDrift)){
  turbo::stop(scenario==Scenario::HardwarePower?turbo::Reason::HardwarePower:turbo::Reason::Power);r.verdict=Verdict::Aborted;return r;
 }
 if(window==WINDOW_S&&((scenario==Scenario::BestUnstable&&f==850)||scenario==Scenario::AllUnstable)){r.verdict=Verdict::Errors;return r;}
 if(scenario==Scenario::Power&&f>=850)r.pmax=25;
 if((scenario==Scenario::Errors&&f>=850)||scenario==Scenario::Voltage||(scenario==Scenario::NeedVoltage&&f>=850&&mv<1240))r.verdict=Verdict::Errors;
 return r;
}
''' + s[b:]
s = change(s, 'static void reset(){probe_f.clear();', 'static void reset(){hold_samples=0;hold_f.clear();turbo::candidates.clear();turbo::selected.clear();turbo::fatal=false;probe_f.clear();')
s = change(s, 'best_mv==1190&&probe_windows.back()==WINDOW_S', 'best_mv==1220&&probe_windows.back()==WINDOW_S')
s = change(s, ' reset();fail_pll=825;run_turbo_phase();', r'''
 // Crossing only the software budget selects and fully remeasures a proven
 // lower point, then continues mining for several complete HOLD windows.
 reset();scenario=Scenario::SoftPower;run_turbo_phase();
 assert(turbo::selected.size()==1&&turbo::selected[0]==850);
 assert(hold_f.size()>=4);for(auto point:hold_f)assert(point==850);
 assert(!turbo::active()&&f==786&&turbo::reason()==turbo::Reason::User);
 bool fully_verified=false;for(unsigned i=0;i<probe_f.size();i++)if(probe_f[i]==850&&probe_windows[i]==WINDOW_S)fully_verified=true;assert(fully_verified);

 // A high performance point failing its repeated measurement gives the next
 // measured point a chance; it cannot be pinned on its old high score.
 reset();scenario=Scenario::BestUnstable;run_turbo_phase();
 assert(turbo::selected.size()==1&&turbo::selected[0]==838&&!hold_f.empty());
 for(auto point:hold_f)assert(point==838);

 // Every rejected pair is visited at most once, then the safe anchor is used.
 reset();scenario=Scenario::AllUnstable;run_turbo_phase();
 assert(turbo::selected.empty()&&hold_f.empty()&&f==786&&mv==1170);
 assert(probe_f.size()<30);

 // Actual hardware power fault never enters candidate revalidation or HOLD.
 reset();scenario=Scenario::HardwarePower;run_turbo_phase();
 assert(turbo::selected.empty()&&hold_f.empty()&&f==786&&turbo::reason()==turbo::Reason::HardwarePower);
 for(auto window:probe_windows)assert(window==FAST_WINDOW_S);

 // HOLD drift is recovered only to a lower fully revalidated candidate, with
 // no climb/recover loop and no unmeasured fallback used for sustained mining.
 reset();scenario=Scenario::HoldDrift;run_turbo_phase();
 assert(turbo::selected.size()==2&&turbo::selected[0]==850&&turbo::selected[1]==838);
 assert(!hold_f.empty()&&hold_f.front()==850&&hold_f.back()==838);
 reset();scenario=Scenario::Frequency;fail_pll=825;run_turbo_phase();''')
s = change(s, "print('PASS production tuner apply/climb/TURBO phase: stepwise max1000 vs power stop,1300mV bound, stable fallback/stock restore, failed-write ordering, stock800 unchanged')", "print('PASS production tuner phase: soft budget -> verified HOLD; hardware -> safe rollback; unstable -> next; all fail -> anchor; HOLD continues and drift lowers once; PLL/write ordering and stock800')")
p.write_text(s)
print('Installed production-phase full-verification and finite HOLD regressions')

# Keep API schema validation strict as the two diagnostic keys are introduced.
import json
import yaml
p = root / 'overlay/docs/native-api.json'
doc = json.loads(p.read_text())
get = doc['paths']['/api/turbo']['get']
schema = get['responses']['200']['content']['application/json']['schema']
schema['properties']['totalSteps'] = {'type': 'integer', 'minimum': 0, 'description': 'Total completed or aborted measurement attempts in this search; trials retains the last 16.'}
schema['properties']['storageError'] = {'type': 'integer', 'description': 'Last NVS read/write/commit error; zero means success.'}
schema['required'].extend(['totalSteps', 'storageError'])
p.write_text(json.dumps(doc, indent=2) + '\n')
p = root / 'upstream/docs/openapi.yaml'
merged = yaml.safe_load(p.read_text())
merged['paths']['/api/turbo']['get'] = get
p.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True))
print('Documented totalSteps/storageError without weakening strict API schemas')
