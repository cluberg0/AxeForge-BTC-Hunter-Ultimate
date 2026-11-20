#!/usr/bin/env python3
"""Retain confirmed results across searches without restoring probe clocks."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
for base in (root / 'upstream/main', root / 'overlay/main'):
    p = base / 'core/turbo.cpp'
    s = p.read_text()
    old = 'Point anchor_point,seed;'
    assert s.count(old) == 1
    s = s.replace(old, 'Point confirmed_point,anchor_point,seed;')
    old = 'void verified(uint16_t f,uint16_t mv,float ghs,float watts){best_f=f;best_mv=mv;best_score=ghs;best_watts=watts;}'
    new = '''void verified(uint16_t f,uint16_t mv,float ghs,float watts){
 Guard g;if(!g.ok)return;
 // Only remember()'s fully validated archive can become a retained winner.
 // better() also sees short probes, which must not survive the next search.
 for(const auto&p:archive.points)if(turbo_math::valid(p)&&p.mhz==f&&p.mv==mv&&p.cap==requested_cap.load()){
  confirmed_point=p;best_f=f;best_mv=mv;best_score=ghs;best_watts=watts;return;
 }
}'''
    assert s.count(old) == 1
    s = s.replace(old, new)
    p.write_text(s)
print('V3 recovery: retain confirmed result metadata, remeasure seeds, preserve immediate PSU guards')
