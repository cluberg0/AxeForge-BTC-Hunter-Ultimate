#!/usr/bin/env python3
"""Differential-test actual legacy PLL loop and production high-frequency ramp."""
import pathlib,tempfile,subprocess
root=pathlib.Path(__file__).resolve().parents[1]
old=subprocess.check_output(['git','-C',str(root/'upstream'),'show','e84c651c36a4b5f91c537577704245ded032592d:main/asic/bm13xx.cpp'],text=True)
a=old.index('    float min_diff = 2.0f;');b=old.index('\n#endif',a);solver=old[a:b]
s=(root/'upstream/main/asic/bm13xx.cpp').read_text();a=s.index('static bool ramp_chain(');b=s.index('\nbool set_frequency',a);ramp=s[a:b]
code=r'''
#include <cassert>
#include <vector>
#include <cmath>
#include "asic/bm1370_pll.h"
#define AF_ASIC_BM1370 1
#define ESP_LOGI(...) ((void)0)
#define pdMS_TO_TICKS(x) (x)
static float s_freq=800,fail_at=-1;static unsigned delays=0;static std::vector<float>writes;
void vTaskDelay(unsigned ms){assert(ms==100||ms==200);delays++;}
static bool send_pll(float target){if(target==fail_at)return false;auto p=bm1370_pll::solve(target);if(!p)return false;writes.push_back(target);s_freq=target;return true;}
static bm1370_pll::Plan old_solve(float target){
'''+solver+r'''
 return {best_ref,best_fb,best_p1,best_p2,best_f};}
'''+ramp+r'''
int main(){
 for(int i=800;i<=8000;i++){float f=i/8.f;auto a=bm1370_pll::solve(f),b=old_solve(f);assert(a.fb==b.fb&&a.ref==b.ref&&a.p1==b.p1&&a.p2==b.p2&&a.actual==b.actual);}
 assert(!bm1370_pll::solve(NAN)&&!bm1370_pll::solve(1000.1f));
 assert(old_solve(806.25f)&&old_solve(806.25f).actual!=806.25f); // legacy targets are approximated, not unsupported
 for(float f=800;f<=1000;f+=12.5f){auto p=bm1370_pll::solve(f);assert(p&&p.actual==f);}
 assert(ramp_chain(1000)&&s_freq==1000&&delays<=17);assert(writes.front()==812.5f);
 writes.clear();delays=0;assert(ramp_chain(786)&&s_freq==786&&delays<=19);
 s_freq=800;writes.clear();fail_at=850;assert(!ramp_chain(900)&&s_freq==837.5f);fail_at=-1;assert(ramp_chain(786));
 for(unsigned f=800;f<1000;f+=25){assert(bm1370_pll::next_point(f,1000)==f+25);}
 assert(bm1370_pll::next_point(1000,1000)==0);assert(bm1370_pll::next_point(786,1000)==800);assert(bm1370_pll::next_point(525,1000)==550);assert(bm1370_pll::next_point(595,1000)==600);
}
'''
with tempfile.TemporaryDirectory()as d:
 p=pathlib.Path(d)/'test.cpp';p.write_text(code);e=pathlib.Path(d)/'test';subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(root/'overlay/main'),str(p),'-o',str(e)],check=True);subprocess.run([str(e)],check=True)
print('PASS PLL:7201 exact legacy-loop vectors;806.25 approximated,800..1000 by12.5 exact; production ramp, partial-failure recovery,25MHz tuner targets')
