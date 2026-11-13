#!/usr/bin/env python3
"""Run production tuner apply/climb/TURBO phase with deterministic measurement/driver fakes."""
import pathlib,tempfile,subprocess
r=pathlib.Path(__file__).resolve().parents[1];s=(r/'upstream/main/core/tuner.cpp').read_text()
def between(a,b):return s[s.index(a):s.index(b,s.index(a))]
defs=between('#define FREQ_STEP','// The highest readings')
apply=between('static bool apply(','static Result measure(')
climb=between('static bool climb(','// Phase 2:')
phase=between('static turbo::Reason turbo_wall_reason()','static void tuner_task(')
code=r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include <vector>
#include <string>
#include <cmath>
#include "core/turbo.h"
#include "asic/bm1370_pll.h"
#define ESP_LOGI(...) ((void)0)
#define CONFIG_AF_MAX_CHIP_TEMP 68
'''+defs+r'''
enum class TunerPhase{Measuring,StepUp,Locked};enum class TunerWall{None,Gate,MvGate,Thermal,Power,Errors,Hold,Peak};
struct TunerState{TunerPhase phase=TunerPhase::Locked;unsigned steps_done=0;uint16_t trial_freq=0,trial_mv=0,best_freq=0,best_mv=0;float best_ghs=0;TunerWall wall=TunerWall::None;char note[160]{};};
struct{TunerState tuner;float expected_ghs=1600;}g_state;
struct Settings{int tune_goal=1;bool autotune=true;uint16_t freq_mhz=786,core_mv=1170,power_cap_w=25,tuned_freq=786;};static Settings cfg;
namespace settings{Settings&get(){return cfg;}}
static bool s_restart=false;static unsigned f=786,mv=1170,voltage_max_seen=0;static bool powered=true,fail_voltage=false;static unsigned fail_pll=0;static std::vector<std::string>calls;
namespace board{struct Limits{float vr_ceil_c=80;};const Limits&limits(){static Limits l;return l;}uint16_t core_mv(){return mv;}uint16_t freq_mhz(){return f;}bool is_powered(){return powered;}void shutdown(){powered=false;}uint16_t clamp_mv(int v){return uint16_t(v>1300?1300:v);}uint16_t clamp_freq(int v){return uint16_t(v>(turbo::active()?1000:800)?(turbo::active()?1000:800):v);}bool set_core_mv(uint16_t v){calls.push_back("V"+std::to_string(v));if(fail_voltage)return false;mv=v;voltage_max_seen=v>voltage_max_seen?v:voltage_max_seen;return true;}bool set_freq_mhz(uint16_t v){calls.push_back("F"+std::to_string(v));if(v==fail_pll)return false;f=v;return true;}}
namespace gates{uint16_t max_freq(){return turbo::active()?1000:800;}uint16_t max_mv(){return 1300;}}
namespace turbo{static bool on=true,stop_flag=false,queued=true;static Reason why=Reason::None;static Point anchor;bool active(){return on;}bool cancelled(){return stop_flag;}bool pending(){return queued;}uint16_t max_frequency(){return 1000;}float power_budget(){return 25;}bool check(){return !stop_flag;}void changing(){}Reason reason(){return why;}void stop(Reason r){why=r;stop_flag=true;}bool begin(Point&a){queued=false;on=true;stop_flag=false;why=Reason::None;a=anchor={786,1170,23,1550,1500,1790000000,30,100};return true;}bool remember(uint16_t,uint16_t,float,float,float,float){return true;}void holding(Reason r){why=r;stop_flag=false;}void finish(){on=false;queued=false;stop_flag=false;}Point fallback(uint16_t,float){return anchor;}}
static uint16_t held(uint16_t x){return x;}static void fresh_readout(){g_state.tuner.wall=TunerWall::None;}static void peaks(const Result&){}static void note(const char*,float=0,float=0){}static const char*verdict_text(Verdict){return "test";}static void wall(TunerWall w,uint16_t,uint16_t,bool=false){g_state.tuner.wall=w;}static TunerWall verdict_wall(Verdict v){return v==Verdict::Power?TunerWall::Power:v==Verdict::Thermal?TunerWall::Thermal:TunerWall::Errors;}static float joules_per_th(const Result&r){return r.pavg/(r.ghs/1000);}
static float power_ceiling(){return 25;}enum class Scenario{Frequency,Power,Errors,Pll};static Scenario scenario=Scenario::Frequency;
static Result measure(int,int,float,float){if(g_state.tuner.phase==TunerPhase::Locked){turbo::stop(turbo::Reason::User);return {Verdict::Aborted,0,0,0,0,0,0,0,0};}Result r{Verdict::Stable,float(f*2),0,0,55,60,22,22,20};if(scenario==Scenario::Power&&f>=850)r.pmax=24.5;if(scenario==Scenario::Errors&&f>=850)r.verdict=Verdict::Errors;return r;}
'''+apply+climb+phase+r'''
static void reset(){cfg=Settings{};f=786;mv=1170;powered=true;fail_voltage=false;fail_pll=0;s_restart=false;calls.clear();voltage_max_seen=0;g_state.tuner=TunerState{};turbo::on=true;turbo::stop_flag=false;turbo::queued=true;turbo::why=turbo::Reason::None;}
int main(){
 reset();uint16_t best=786,best_mv=1170;float ghs=0;assert(climb(best,best_mv,ghs));assert(best==1000&&best_mv==1170&&f==1000); // requested max can be explored, not forced
 reset();scenario=Scenario::Power;best=786;best_mv=1170;ghs=0;assert(climb(best,best_mv,ghs));assert(best==850&&g_state.tuner.wall==TunerWall::Power&&f==850);
 reset();scenario=Scenario::Errors;mv=1290;best=786;best_mv=1290;ghs=0;assert(climb(best,best_mv,ghs));assert(best==825&&voltage_max_seen==1300&&g_state.tuner.wall==TunerWall::MvGate);
 reset();scenario=Scenario::Frequency;run_turbo_phase();assert(!turbo::active()&&f==786&&mv==1170&&cfg.tuned_freq==786&&cfg.power_cap_w==25); // same task restores stock state, not NVS Turbo clock
 reset();fail_pll=825;run_turbo_phase();assert(!turbo::active()&&f==786&&turbo::reason()==turbo::Reason::Pll);
 reset();fail_voltage=true;assert(!apply(825,1180));assert(f==786&&calls.size()==1&&calls[0]=="V1180"); // never overclock after failed voltage raise
 reset();f=900;mv=1150;assert(apply(786,1170,true));assert(calls.size()==2&&calls[0]=="F786"&&calls[1]=="V1170");
 reset();f=900;mv=1170;fail_pll=786;assert(!apply(786,1150,true));assert(mv==1170&&calls.size()==1); // no undervolt after failed downclock
 reset();turbo::on=false;best=786;best_mv=1170;ghs=0;assert(climb(best,best_mv,ghs)&&best<=800);
}
'''
with tempfile.TemporaryDirectory()as d:
 p=pathlib.Path(d)/'test.cpp';p.write_text(code);e=pathlib.Path(d)/'test';subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(r/'tests/stubs'),'-I'+str(r/'overlay/main'),str(p),'-o',str(e)],check=True);subprocess.run([str(e)],check=True)
print('PASS production tuner apply/climb/TURBO phase: stepwise max1000 vs power stop,1300mV bound, stable fallback/stock restore, failed-write ordering, stock800 unchanged')
