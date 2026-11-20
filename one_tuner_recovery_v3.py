#!/usr/bin/env python3
"""Conservative recovery: preserve verified result; debounce one-sample PSU spikes."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'upstream/main/core/turbo.cpp'
s=p.read_text()
a='std::atomic<unsigned> limit{1000},requested_cap{30},state{0};'
assert s.count(a)==1
s=s.replace(a,a+'\nstd::atomic<unsigned> power_watch_samples{0};')
a='if(std::isfinite(g_state.pin)&&g_state.pin>std::min(float(requested_cap.load()),std::min(psu_watts.load(),5.f*psu_amps.load())))return Reason::Power;'
b='''// Debounce a single ADC spike; sustained excess still trips.
 float cap=std::min(float(requested_cap.load()),std::min(psu_watts.load(),5.f*psu_amps.load()));
 if(std::isfinite(g_state.pin)&&g_state.pin>cap){
   if(++power_watch_samples>=2)return Reason::Power;
 }else power_watch_samples=0;'''
assert s.count(a)==1
s=s.replace(a,b)
a='best_score=0;best_f=0;best_mv=0;best_watts=0;trial_count=0;'
assert s.count(a)==1
s=s.replace(a,'trial_count=0;power_watch_samples=0;')
p.write_text(s)
print('V3: PSU spike debounce and verified result retention')
