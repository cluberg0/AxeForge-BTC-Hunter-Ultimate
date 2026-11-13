#!/usr/bin/env python3
"""Production Gamma clock reporting and power-read freshness under injected failures."""
import pathlib,tempfile,subprocess
r=pathlib.Path(__file__).resolve().parents[1];s=(r/'upstream/main/core/board_bitaxe.cpp').read_text();a=s.index('bool set_freq_mhz(');b=s.index('\nuint16_t core_mv()',a);clock=s[a:b];a=s.index('        float v = tps546::vin();');b=s.index('\n    }\n    // DS4432U path',a);power=s[a:b]
code=r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <math.h>
#define AF_INA260 0
#define POWER_OFFSET_W 5.0f
struct{int chips_detected=1;uint16_t freq_mhz=786;float expected_ghs=1600,vin=5.1f,vout=1.17f,iout=0,pin=0,iin=0;std::atomic<uint32_t>power_sample_ms{0};}g_state;
static bool s_powered=true,fail_pll=false;static uint16_t s_freq=786,ceiling=1000;static float programmed=786;
struct Guard{Guard(){}~Guard(){}};
namespace asic{constexpr int SMALL_CORES=2040;int offset_total(){return 0;}float frequency(){return programmed;}bool set_frequency(uint16_t f){programmed=fail_pll?825.f:float(f);return !fail_pll;}}
namespace board{uint16_t clamp_freq(int f){return f>ceiling?ceiling:uint16_t(f);}
'''+clock+r'''
}
static int64_t now=1000000;int64_t esp_timer_get_time(){return now;}
namespace tps546{static float v=5.1f,vo=1.17f,i=15,p=17;float vin(){return v;}float vout(){return vo;}float iout(){return i;}float pout(){return p;}}
static void sample_power(){
'''+power+r'''
}
int main(){
 fail_pll=true;assert(!board::set_freq_mhz(900)&&s_freq==825&&g_state.freq_mhz==825); // report partial ramp, not stale786
 fail_pll=false;assert(board::set_freq_mhz(786)&&s_freq==786);ceiling=800;assert(board::set_freq_mhz(1000)&&s_freq==800);s_powered=false;assert(!board::set_freq_mhz(900)&&s_freq==800);
 sample_power();assert(g_state.power_sample_ms.load()==1000&&g_state.pin==22);
 now+=4000000;tps546::v=NAN;sample_power();assert(g_state.vin==5.1f&&g_state.power_sample_ms.load()==1000); // retained value cannot impersonate fresh power telemetry
 tps546::v=5.1f;tps546::p=NAN;sample_power();assert(g_state.power_sample_ms.load()==1000);
 tps546::p=17;tps546::i=NAN;sample_power();assert(g_state.power_sample_ms.load()==1000);
 tps546::i=15;sample_power();assert(g_state.power_sample_ms.load()==5000);
}
'''
with tempfile.TemporaryDirectory()as d:
 p=pathlib.Path(d)/'test.cpp';p.write_text(code);e=pathlib.Path(d)/'test';subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(p),'-o',str(e)],check=True);subprocess.run([str(e)],check=True)
print('PASS production Gamma board: partial PLL failure reporting, stock cap/off guard, power freshness never renewed by retained/failed sensor reads')
