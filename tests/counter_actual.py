#!/usr/bin/env python3
"""Run production counter sampling against wrap, reset and timestamp edge vectors."""
import pathlib,subprocess,tempfile,sys
root=pathlib.Path(__file__).resolve().parents[1]
source=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else root/'upstream/main/mining/miner.cpp';fixed=len(sys.argv)<3 or sys.argv[2]!='baseline'
s=source.read_text();a=s.index('static void on_counter(');b=s.index('// The chain occasionally',a);body=s[a:b]
harness=r'''
#include <atomic>
#include <cassert>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <cstdio>
#include "core/hunter_math.h"
#define AF_NUM_ASICS 1
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
#define ESP_LOGW(...) (++warnings)
static int warnings=0;
static std::atomic<bool>s_reset_counters{false};
static int64_t s_prev_t[1]{},s_prev_err_t[1]{},s_win_us[1]{};
static uint32_t s_prev_cnt[1]{},s_prev_err[1]{};
static double s_win_err[1]{},s_win_valid[1]{};
struct State{std::atomic<uint32_t>hash_counter_ms{0};float chip_ghs[1]{},chip_err_ghs[1]{};}g_state;
static int64_t tick=1000000;int64_t esp_timer_get_time(){return tick;}
'''+('constexpr bool fixed=true;\n' if fixed else 'constexpr bool fixed=false;\n')+body+r'''
int main(){
 on_counter(0,1000,false);tick+=3000000;on_counter(0,2000,false);assert(g_state.chip_ghs[0]>1400&&g_state.chip_ghs[0]<1500);double window=s_win_valid[0];on_counter(0,50,true);
 tick+=3000000;on_counter(0,1,false);assert(warnings==1&&g_state.hash_counter_ms.load()==0&&s_win_valid[0]==window&&s_prev_cnt[0]==1);
 tick+=3000000;on_counter(0,1001,false);assert(g_state.chip_ghs[0]>1400&&s_win_valid[0]==window+1000);
 on_counter(0,1,true);double reset_errors=s_win_err[0];assert(fixed?reset_errors==0:reset_errors>1e9);s_win_err[0]=0;
 std::printf("{\"fixed\":%s,\"validWindow\":%.0f,\"resetErrorWindow\":%.0f,\"asicGHs\":%.3f}\n",fixed?"true":"false",s_win_valid[0],reset_errors,g_state.chip_ghs[0]);
 s_prev_cnt[0]=UINT32_MAX-499;s_prev_t[0]=tick;tick+=3000000;on_counter(0,500,false);assert(g_state.chip_ghs[0]>1400&&g_state.chip_ghs[0]<1500&&warnings==1);
 auto total=s_win_valid[0];on_counter(0,501,false);assert(s_win_valid[0]==total);s_reset_counters=true;tick+=1;on_counter(0,0,false);assert(s_win_valid[0]==total&&g_state.hash_counter_ms.load()==0);
 tick+=3000000;on_counter(0,1000,true);tick+=3000000;on_counter(0,2000,true);assert(s_win_err[0]==1000&&g_state.chip_err_ghs[0]>1400); // real error counts remain visible
 on_counter(-1,0,false);on_counter(1,0,false);
}
'''
with tempfile.TemporaryDirectory() as d:
 p=pathlib.Path(d)/'test.cpp';p.write_text(harness);exe=pathlib.Path(d)/'test'
 subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(root/'overlay/main'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('PASS production counter: genuine uint32 wrap, reset/outlier recovery, zero dt, reset request and visible real errors')
