#!/usr/bin/env python3
"""Compile actual gates with deterministic board/PSU/settings collaborators."""
import pathlib,tempfile,subprocess
r=pathlib.Path(__file__).resolve().parents[1]
def stripped(p):return '\n'.join(x for x in p.read_text().splitlines() if not x.startswith('#include')and x!='#pragma once')
code='''#include <cstdint>
namespace psu{enum class Level{Unknown,Ok,Weak,Bad};struct State{Level level=Level::Ok;};State s;const State&state(){return s;}}
namespace settings{struct Settings{bool overclock=false;};Settings cfg;Settings&get(){return cfg;}}
namespace board{struct Limits{uint16_t max_freq_mhz=800;float max_power_w=40;};Limits l;const Limits&limits(){return l;}uint16_t max_mv(){return 1300;}bool is_rev7(){return false;}}
namespace turbo{bool supported(){return true;}}
'''+stripped(r/'upstream/main/core/gates.h')+'\n'+stripped(r/'upstream/main/core/gates.cpp')+'''
#include <cassert>
int main(){assert(gates::available());assert(gates::max_freq()==800&&gates::max_mv()==1300);settings::cfg.overclock=true;assert(gates::active()&&gates::max_freq()==1000&&gates::max_mv()==1300&&gates::max_power()==40);psu::s.level=psu::Level::Weak;assert(!gates::active()&&gates::max_freq()==800&&settings::cfg.overclock);psu::s.level=psu::Level::Ok;settings::cfg.overclock=false;assert(gates::max_freq()==800&&gates::stock_max_power()==40);}
'''
with tempfile.TemporaryDirectory()as d:
 p=pathlib.Path(d)/'g.cpp';p.write_text(code);exe=pathlib.Path(d)/'g';subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('PASS real native gates: Gamma available, stock800 vs unlocked1000,1300mV unchanged, weak PSU pauses, board hard power unchanged')
