#!/usr/bin/env python3
"""Explicit Gamma-only experimental extension, after validated2.0 patch chain."""
import pathlib,sys
r=pathlib.Path(sys.argv[1])
def patch(name,a,b):
 p=r/name;s=p.read_text();assert s.count(a)==1,(name,a[:70],s.count(a));p.write_text(s.replace(a,b))
patch('main/asic/bm13xx.cpp','#include "bm13xx.h"','#include "bm13xx.h"\n#include "asic/bm1370_pll.h"')
a='''    float min_diff = 2.0f;
    int best_ref = 0, best_fb = 0, best_p1 = 0, best_p2 = 0, pmin = 255, p2min = 255;'''
b='''#if AF_ASIC_BM1370
    auto plan=bm1370_pll::solve(target);
    int best_ref=plan.ref,best_fb=plan.fb,best_p1=plan.p1,best_p2=plan.p2;
    float best_f=plan.actual;
#else
'''+a
patch('main/asic/bm13xx.cpp',a,b)
patch('main/asic/bm13xx.cpp','''    }
#endif
    if (!best_fb)''','''    }
#endif // BM1370 pure planner
#endif
    if (!best_fb)''')
# Above800MHz use exact12.5MHz PLL frequencies rather than approximate6.25MHz targets.
patch('main/asic/bm13xx.cpp','    const float step = 6.25f;','''    const float step =
#if AF_ASIC_BM1370
        (target>800 || s_freq>800) ? 12.5f :
#endif
        6.25f;''')
# Keep the original ramp slew limit:12.5MHz/200ms above800,6.25MHz/100ms in stock.
p=r/'main/asic/bm13xx.cpp';s=p.read_text();a=s.index('static bool ramp_chain(');b=s.index('\nbool set_frequency',a);part=s[a:b];part=part.replace('pdMS_TO_TICKS(100)','pdMS_TO_TICKS(step>6.25f?200:100)');p.write_text(s[:a]+part+s[b:])
patch('main/asic/bm13xx.h','float frequency();','float frequency();\nbool pll_supported(float target,float &actual);')
patch('main/asic/bm13xx.cpp','float frequency() { return s_freq; }','''float frequency() { return s_freq; }
bool pll_supported(float target,float &actual) {
#if AF_ASIC_BM1370
    auto p=bm1370_pll::solve(target);actual=p.actual;return bool(p);
#else
    (void)target;actual=0;return false;
#endif
}''')
# Keep the board's reported programmed clock honest after a partial ramp failure.
patch('main/core/board_bitaxe.cpp','''    if (!asic::set_frequency(mhz)) return false;
    s_freq = mhz;
    g_state.freq_mhz = mhz;''','''    bool ok=asic::set_frequency(mhz);
    s_freq = (uint16_t)lroundf(asic::frequency());
    g_state.freq_mhz = s_freq;''')
patch('main/core/board_bitaxe.cpp','''    g_state.expected_ghs = (mhz * g_state.chips_detected + asic::offset_total()) * (float) asic::SMALL_CORES / 1000.0f;
    return true;''','''    g_state.expected_ghs = (s_freq * g_state.chips_detected + asic::offset_total()) * (float) asic::SMALL_CORES / 1000.0f;
    return ok;''')
patch('main/core/state.h','    std::atomic<uint32_t> telemetry_ms{0};','    std::atomic<uint32_t> power_sample_ms{0}; // all power channels read successfully\n    std::atomic<uint32_t> telemetry_ms{0};')
patch('main/core/board_bitaxe.cpp','''            g_state.pin = iw;
            return;''','''            g_state.pin = iw;
            g_state.power_sample_ms.store((uint32_t)(esp_timer_get_time()/1000));
            return;''')
patch('main/core/board_bitaxe.cpp','''        g_state.iin = g_state.vin > 1 ? g_state.pin / g_state.vin : 0;
        return;''','''        g_state.iin = g_state.vin > 1 ? g_state.pin / g_state.vin : 0;
        if(isfinite(v)&&isfinite(vo)&&isfinite(g_state.iout)&&isfinite(p)&&v>0&&vo>0&&g_state.iout>0&&p>0)
            g_state.power_sample_ms.store((uint32_t)(esp_timer_get_time()/1000));
        return;''')
# No change to board/Kconfig limits: stock stays800, only an active manual session opens the gate.
patch('main/core/gates.cpp','#include "gates.h"','#include "gates.h"\n#include "core/turbo.h"')
patch('main/core/gates.cpp','uint16_t max_freq() { return stock_max_freq() + (active() ? env_freq() : 0); }','uint16_t max_freq() { return turbo::active()?turbo::max_frequency():stock_max_freq() + (active() ? env_freq() : 0); }')
patch('main/core/gates.cpp','    int mv = stock_max_mv() + (active() ? env_mv() : 0);','    int mv = stock_max_mv() + (active() ? env_mv() : 0);\n    if(turbo::active() && mv>1300)mv=1300;')
patch('main/stratum/pools.h','void start();','void start();\nuint32_t session_id(int pool);')
patch('main/stratum/pools.cpp','namespace pools {\n\nvoid start()','namespace pools {\nuint32_t session_id(int i){return i>=0&&i<AF_MAX_POOLS?s_pools[i].session.load():0;}\n\nvoid start()')
patch('main/main.cpp','#include "core/intelligence.h"','#include "core/intelligence.h"\n#include "core/turbo.h"')
patch('main/main.cpp','    intel::start();','    turbo::start();\n    intel::start();')
patch('main/core/monitor.cpp','#include "core/intelligence.h"','#include "core/intelligence.h"\n#include "core/turbo.h"')
patch('main/core/monitor.cpp','            // ---- hard limits: these cut power, no questions asked ----','''            // Extra experimental fail-safe; original hard limits remain below unchanged.
            auto trip=turbo::monitor_trip();
            if(trip!=turbo::Reason::None){turbo::disarm(trip);emergency(SysStatus::Fault,"TURBO watchdog / PSU budget");continue;}
            // ---- hard limits: these cut power, no questions asked ----''')
patch('main/net/web.cpp','#include "core/net_health.h"','#include "core/net_health.h"\n#include "core/turbo.h"')
patch('main/net/web.cpp','    cfg.max_uri_handlers = 44;','    cfg.max_uri_handlers = 46;')
patch('main/net/web.cpp','        {"/api/network", HTTP_GET, net_health::get, NULL},','        {"/api/network", HTTP_GET, net_health::get, NULL},\n        {"/api/turbo", HTTP_GET, turbo::get, NULL},\n        {"/api/turbo", HTTP_POST, turbo::set, NULL},')
patch('main/net/web.cpp','    return ((handler_fn) req->user_ctx)(req);','''    if(req->method==HTTP_POST && turbo::engaged()){
        const char*blocked[]={"/api/settings","/api/pools","/api/retune","/api/hunter","/api/ota","/api/update","/api/selftest"};
        for(auto path:blocked)if(!strncmp(req->uri,path,strlen(path)))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Stop TURBO before changing hardware/transport or starting another experiment");
    }
    return ((handler_fn) req->user_ctx)(req);''')
# Direct manual settings stay stock even when the tuner-only gate is open.
patch('main/net/web.cpp','    cJSON *requested_cap = cJSON_GetObjectItem(j,"pcap");','''    cJSON *manual_f=cJSON_GetObjectItem(j,"freq");
    if(cJSON_IsNumber(manual_f) && manual_f->valuedouble>800){cJSON_Delete(j);return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Above800MHz only through explicit TURBO session");}
    cJSON *requested_cap = cJSON_GetObjectItem(j,"pcap");''')
patch('main/core/tuner.cpp','#include "core/intelligence.h"','#include "core/intelligence.h"\n#include "core/turbo.h"\n#include "asic/bm1370_pll.h"')
patch('main/core/tuner.cpp','static bool should_abort() { return s_restart || !settings::get().autotune || !board::is_powered(); }','static bool should_abort() { return s_restart || !settings::get().autotune || !board::is_powered() || (turbo::pending()&&!turbo::active()) || (turbo::active()&&turbo::cancelled()); }')
patch('main/core/tuner.cpp','    float lim = gates::max_power();','    float lim = gates::max_power();\n    if(turbo::active())return fminf(lim,turbo::power_budget());')
a='''static bool apply(uint16_t freq, uint16_t mv)
{
    freq = board::clamp_freq(held(freq));
    mv = board::clamp_mv(mv);
    g_state.tuner.trial_freq = freq;
    g_state.tuner.trial_mv = mv;
    bool ok = true;
    if (mv > board::core_mv()) ok &= board::set_core_mv(mv);
    if (freq != board::freq_mhz()) ok &= board::set_freq_mhz(freq);
    if (mv < board::core_mv()) ok &= board::set_core_mv(mv);
    return ok;
}'''
b='''static bool apply(uint16_t freq, uint16_t mv,bool recovery=false)
{
    freq=board::clamp_freq(held(freq));mv=board::clamp_mv(mv);
    g_state.tuner.trial_freq=freq;g_state.tuner.trial_mv=mv;
    if(turbo::active()&&!recovery&&(freq>board::freq_mhz()||mv>board::core_mv())&&!turbo::check())return false;
    if(turbo::active()&&freq!=board::freq_mhz())turbo::changing();
    // Downclock first, then any voltage raise; never continue after a failed write.
    if(freq<board::freq_mhz()&&!board::set_freq_mhz(freq)){if(turbo::active())turbo::stop(turbo::Reason::Pll);return false;}
    if(mv>board::core_mv()&&!board::set_core_mv(mv)){if(turbo::active())turbo::stop(turbo::Reason::Supply);return false;}
    if(freq!=board::freq_mhz()&&!board::set_freq_mhz(freq)){if(turbo::active())turbo::stop(turbo::Reason::Pll);return false;}
    if(mv<board::core_mv()&&!board::set_core_mv(mv)){if(turbo::active())turbo::stop(turbo::Reason::Supply);return false;}
    return true;
}'''
patch('main/core/tuner.cpp',a,b)
patch('main/core/tuner.cpp','        if (should_abort()) {','        if ((turbo::active()&&!turbo::check()) || should_abort()) {')
patch('main/core/tuner.cpp','        if (t == warmup_s) miner::reset_window();','        if (t == warmup_s) {miner::reset_window();if(turbo::active())turbo::window_begin();}')
patch('main/core/tuner.cpp','    if (r.err > max_err || r.worst_chip > max_chip_err || eff < MIN_EFFICIENCY) r.verdict = Verdict::Errors;','    if (r.err > max_err || r.worst_chip > max_chip_err || eff < MIN_EFFICIENCY) r.verdict = Verdict::Errors;\n    if(turbo::active() && r.verdict==Verdict::Stable && !turbo::window_end(r.ghs))r.verdict=Verdict::Aborted;')
patch('main/core/tuner.cpp','            bool better = eff_goal ? jth < best_jth * (1 - EFF_MARGIN) : r.ghs > best_ghs;','''            if(turbo::active()&&!turbo::remember(f,mv,r.ghs,r.pmax,r.tmax,r.vrmax))return false;
            bool better = turbo::active() || (eff_goal ? jth < best_jth * (1 - EFF_MARGIN) : r.ghs > best_ghs);''')
patch('main/core/tuner.cpp','''            bool at_hold = held(f + FREQ_STEP) != f + FREQ_STEP;
            if (near_thermal || near_power || at_hold || f + FREQ_STEP > gates::max_freq()) {''','''            if(turbo::active())near_thermal=near_thermal||r.tmax>=62||r.vrmax>=70;
            uint16_t next=turbo::active()?uint16_t(bm1370_pll::next_point(f,turbo::max_frequency())):uint16_t(f+FREQ_STEP);
            bool at_hold = next&&held(next)!=next;
            if (near_thermal || near_power || at_hold || !next || next > gates::max_freq()) {''')
patch('main/core/tuner.cpp','''            f += FREQ_STEP;
            g_state.tuner.phase = TunerPhase::StepUp;
            apply(f, mv);''','''            f = next;
            g_state.tuner.phase = TunerPhase::StepUp;
            if(!apply(f,mv))return false;''')
patch('main/core/tuner.cpp','''            note("Errors, raising voltage to %.0f mV", mv);
            apply(f, mv);''','''            note("Errors, raising voltage to %.0f mV", mv);
            if(!apply(f,mv))return false;''')
# New phase uses the SAME apply/measure/climb functions and SAME task, no competing loop/task.
helper=(pathlib.Path(__file__).resolve().parent/'turbo_phase.inc').read_text()
patch('main/core/tuner.cpp','static void tuner_task(void *)',helper+'\nstatic void tuner_task(void *)')
patch('main/core/tuner.cpp','''        Settings &cfg = settings::get();
        static uint16_t seen_freq''','''        Settings &cfg = settings::get();
        if(turbo::pending()){run_turbo_phase();continue;}
        static uint16_t seen_freq''')
(r/'version.txt').write_text('1.4.10-hunter-2.0-TURBO1000\n')
print('Manual TURBO1000 integrated; stock caps/defaults/partitions unchanged')
