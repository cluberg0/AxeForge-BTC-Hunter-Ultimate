#!/usr/bin/env python3
"""Apply native Gamma overlay to exactly upstream AxeForge v1.4.10."""
import pathlib, subprocess, shutil, sys
P=pathlib.Path(__file__).resolve().parent
R=pathlib.Path(sys.argv[1]).resolve()
sha=subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()
assert sha=='e84c651c36a4b5f91c537577704245ded032592d',f'Unexpected upstream commit: {sha}'
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True).strip(),'Upstream checkout not clean'
def patch(name, changes):
 p=R/name;s=p.read_text()
 for a,b in changes:
  assert s.count(a)==1,(name,a[:100],s.count(a));s=s.replace(a,b)
 p.write_text(s)
inc=('#include "core/state.h"','#include "core/state.h"\n#include "core/intelligence.h"')
patch('main/main.cpp',[inc,('    stats::load();','    stats::load();\n    intel::start();  // low-priority history task; no changes to settings namespace')])
patch('main/core/monitor.cpp',[inc,('            if (g_state.chip_temp_max >= CONFIG_AF_MAX_CHIP_TEMP - FAN_BOOST_MARGIN_C)', '            // Optional extra floor for the one-fan Gamma. Never reduces stock duty, never overrides manual mode.\n            if (cfg.fan_mode[0] == 0) duty[0] = fmaxf(duty[0], intel::fan_floor());\n            if (g_state.chip_temp_max >= CONFIG_AF_MAX_CHIP_TEMP - FAN_BOOST_MARGIN_C)')])
patch('main/core/tuner.cpp',[inc,('            best_f = board::clamp_freq(best_f - FREQ_STEP);\n            snprintf(g_state.tuner.note', '''            const uint16_t next_f = board::clamp_freq(best_f - FREQ_STEP);
            uint16_t known_f = next_f, known_mv = best_mv;
            // Only after the original tuner has rejected a locked error window.
            // A known lower point can never increase frequency or voltage.
            if (r.verdict == Verdict::Errors && cfg.tune_goal == GOAL_POWER_CAP && !any_offset() &&
                intel::rollback_point(best_f, best_mv, next_f, cfg.power_cap_w, known_f, known_mv) &&
                !should_abort() && apply(known_f, known_mv)) {
                best_f = held(known_f); best_mv = known_mv;
                ESP_LOGW(TAG, "intelligence: returned to prior measured point %u MHz @ %u mV", best_f, best_mv);
                lock_point(best_f, best_mv, 0);  // next stock watch window measures it again
                g_state.tuner.phase = TunerPhase::Locked;
                continue;
            }
            best_f = next_f;
            snprintf(g_state.tuner.note''')])
patch('main/net/web.cpp',[inc,('        {"/api/status", HTTP_GET, status_get, NULL},','        {"/api/status", HTTP_GET, status_get, NULL},\n        {"/api/intelligence", HTTP_GET, intel::get, NULL},\n        {"/api/intelligence", HTTP_POST, intel::set, NULL},'),('    cfg.max_uri_handlers = 36;','    cfg.max_uri_handlers = 38;')])
# CMake GLOB_RECURSE includes new .cpp; EMBED_TXTFILES embeds the HTML at link time.
shutil.copytree(P/'overlay',R,dirs_exist_ok=True)
subprocess.run([sys.executable,str(P/"patch_hunter.py"),str(R)],check=True)
subprocess.run(['git', '-C', str(R), 'apply', str(P/'integration-hardening.patch')], check=True)
subprocess.run([sys.executable, str(P/'patch_api_safety.py'), str(R)], check=True)
subprocess.run([sys.executable, str(P/'patch_guardian.py'), str(R)], check=True)
subprocess.run([sys.executable, str(P/'patch_v2.py'), str(R)], check=True)
subprocess.run([sys.executable, str(P/'patch_turbo.py'), str(R)], check=True)
print('Patched pinned upstream. Build Gamma only.')
