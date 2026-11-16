#!/usr/bin/env python3
"""FASTSEARCH overlay, applied after the verified ONESEARCH package."""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
up = root / "upstream"
p = up / "main/core/tuner.cpp"
s = p.read_text()

def replace_once(text, old, new):
    assert text.count(old) == 1, (old[:100], text.count(old))
    return text.replace(old, new, 1)

# Keep the original full measurement for final validation and stock tuning.
s = replace_once(s, "#define WINDOW_S 300", "#define FAST_WARMUP_S 30\n#define FAST_WINDOW_S 120\n#define WINDOW_S 300")

a = s.index("static bool turbo_confirm(")
b = s.index("// Phase 1: climb.", a)
s = s[:a] + r'''// The climb uses short probes; only the selected point is fully validated.
// Keep every original measurement/telemetry/PSU/temperature/PLL guard.
static bool turbo_confirm(Result &r,uint16_t f,uint16_t &mv)
{
    auto full=[&](uint16_t voltage){
        g_state.tuner.phase=TunerPhase::Measuring;
        note("Final verify %.0f MHz @ %.0f mV",f,voltage);
        Result x=measure(WARMUP_S,WINDOW_S,MAX_ERR_PCT,WORST_CHIP_PCT);
        g_state.tuner.steps_done++;peaks(x);
        return x;
    };
    r=full(mv);
    if(r.verdict!=Verdict::Stable || turbo::cancelled())return false;
    // Bounded final-only voltage trim. Every retained setting is fully measured.
    for(unsigned i=0;i<3 && mv>=board::clamp_mv(0)+MV_STEP;i++){
        const uint16_t prior=mv,candidate=uint16_t(mv-MV_STEP);
        const float previous_ghs=r.ghs;
        if(!apply(f,candidate))return false;
        Result lower=full(candidate);
        if(lower.verdict==Verdict::Stable&&!turbo::cancelled()&&lower.ghs>=previous_ghs*.98f){
            mv=candidate;r=lower;continue;
        }
        // Never recover from a fatal, user, sensor, thermal or PSU fault.
        // Only an ordinary error/throughput failure during an intentional trim
        // may restore the last fully verified voltage at the same frequency.
        const auto why=turbo::reason();
        bool recoverable=lower.verdict==Verdict::Errors ||
            (lower.verdict==Verdict::Stable&&!turbo::cancelled()) ||
            (lower.verdict==Verdict::Aborted&&why==turbo::Reason::Errors);
        if(!recoverable || (turbo::cancelled()&&why!=turbo::Reason::Errors))return false;
        if(!apply(f,prior,true))return false;
        if(turbo::cancelled())turbo::holding(turbo::Reason::Errors);
        if(turbo::cancelled())return false;
        r=full(prior);
        if(r.verdict!=Verdict::Stable||turbo::cancelled())return false;
        break;
    }
    return true;
}

''' + s[b:]

# Short measurements in TURBO only; no per-frequency voltage trim or repeated confirm.
s = replace_once(s,
    "Result r = measure(WARMUP_S, WINDOW_S, MAX_ERR_PCT, WORST_CHIP_PCT);\n        g_state.tuner.steps_done++;",
    "Result r = measure(turbo::active()?FAST_WARMUP_S:WARMUP_S, turbo::active()?FAST_WINDOW_S:WINDOW_S, MAX_ERR_PCT, WORST_CHIP_PCT);\n        g_state.tuner.steps_done++;")
s = replace_once(s, "            if(turbo::active()&&!turbo_confirm(r,f,mv))return false;\n", "")
s = replace_once(s, "            if(turbo::active()&&!turbo::remember(f,mv,r.ghs,r.pmax,r.tmax,r.vrmax))return false;\n", "")
# Do not clear a real fault hold. The existing gate/hold checks stay intact.

a = s.index("    bool can_hold=good&&ghs>0&&!turbo::cancelled();")
b = s.index("    while(can_hold&&board::is_powered()",a)
s = s[:a] + r'''    bool can_hold=good&&ghs>0&&!turbo::cancelled();
    // A power/error wall may terminate a short probe. Restore the best measured
    // candidate, then validate it fully before allowing a sustained hold.
    if(!can_hold&&ghs>0&&board::is_powered()&&(reason==turbo::Reason::Power||reason==turbo::Reason::Errors)){
        if(apply(f,mv,true)){
            turbo::holding(reason);
            can_hold=!turbo::cancelled();
        }
    }
    if(can_hold){
        if(!apply(f,mv,true))can_hold=false;
        else {
            Result verified{};
            if(!turbo_confirm(verified,f,mv)){
                can_hold=false;
                if(turbo::reason()!=turbo::Reason::None)reason=turbo::reason();
            }else if(!turbo::remember(f,mv,verified.ghs,verified.pmax,verified.tmax,verified.vrmax)){
                can_hold=false;reason=turbo::reason();
            }else{
                ghs=verified.ghs;
                g_state.tuner.best_freq=f;g_state.tuner.best_mv=mv;g_state.tuner.best_ghs=ghs;
                turbo::verified(f,mv,ghs,verified.pmax);
                turbo::holding(reason==turbo::Reason::None?turbo_wall_reason():reason);
            }
        }
    }
''' + s[b:]
p.write_text(s)

# Update API best fields to the fully validated, trimmed operating point.
for base in (up / "main", root / "overlay/main"):
    p = base / "core/turbo.h"
    s = p.read_text()
    assert s.count("bool better(")==1
    s = s.replace("bool better(", "void verified(uint16_t f,uint16_t mv,float ghs,float watts);\nbool better(",1)
    p.write_text(s)
    p = base / "core/turbo.cpp"
    s = p.read_text()
    assert s.count("bool better(")==1
    s = s.replace("bool better(", "void verified(uint16_t f,uint16_t mv,float ghs,float watts){best_f=f;best_mv=mv;best_score=ghs;best_watts=watts;}\nbool better(",1)
    p.write_text(s)

# Extend the existing production-code harness; it extracts the actual tuner
# functions, rather than testing a separate algorithm.
p = root / "tests/turbo_phase.py"
s = p.read_text()
s = replace_once(s, "bool better(float,uint16_t){return true;}", "bool better(float,uint16_t){return true;}void verified(uint16_t,uint16_t,float,float){}")
s = replace_once(s, "static Result measure(int,int,float,float){", "static std::vector<unsigned> probe_f,probe_mv;static std::vector<int> probe_windows;static Result measure(int,int window,float,float){probe_f.push_back(f);probe_mv.push_back(mv);probe_windows.push_back(window);")
s = replace_once(s, "static void reset(){", "static void reset(){probe_f.clear();probe_mv.clear();probe_windows.clear();")
s = replace_once(s, "best==1000&&best_mv==1000&&f==1000", "best==1000&&best_mv==1170&&f==1000")
s = replace_once(s, " reset();scenario=Scenario::Power;", r''' reset();scenario=Scenario::Frequency;f=788;mv=1220;best=788;best_mv=1220;ghs=0;
 assert(climb(best,best_mv,ghs)&&best==1000);
 assert(probe_f.size()>=4&&probe_f[0]==788&&probe_f[1]==800&&probe_f[2]==813&&probe_f[3]==825);
 for(unsigned i=0;i<probe_f.size();i++){assert(probe_mv[i]==1220&&probe_windows[i]==FAST_WINDOW_S);if(i)assert(probe_f[i]>probe_f[i-1]);}
 assert(best_mv==1220); // no per-frequency trimming
 Result final{};assert(turbo_confirm(final,best,best_mv));assert(best_mv==1190&&probe_windows.back()==WINDOW_S);
 reset();scenario=Scenario::Power;''')
p.write_text(s)
# The image verifier and synthetic fixtures must enforce the NEW app version.
# Keep all image header, segment, checksum and partition validation intact.
old_version = "1.4.10-hunter-T1000-ONESEARCH"
new_version = "1.4.10-hunter-T1000-FASTSEARCH"
p = root / "verify_image.py"
v = p.read_text()
assert old_version in v, "Expected pinned ONESEARCH image version not found"
p.write_text(v.replace(old_version, new_version))
p = root / "tests/image.py"
v = p.read_text()
p.write_text(v.replace(old_version, new_version))
(up / "version.txt").write_text("1.4.10-hunter-T1000-FASTSEARCH\n")
print("FASTSEARCH overlay applied: 30+120s probes, full final validation, <=3 trim steps, actual 788->800 regression.")
