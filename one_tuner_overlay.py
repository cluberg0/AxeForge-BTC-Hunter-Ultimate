#!/usr/bin/env python3
"""Gamma ONE-TUNER overlay. Applied after fastsearch_overlay.py, not in place of it.

The existing FASTSEARCH engine is the only automatic frequency search on
supported Bitaxe Gamma. Manual fixed-clock operation remains available.
All existing hard safety limits and their watchdogs are preserved.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
up = root / "upstream"

def change_once(src, old, new, label):
    actual = src.count(old)
    assert actual == 1, (label, actual)
    return src.replace(old, new, 1)

p = up / "main/core/tuner.cpp"
s = p.read_text()
original = """        if(turbo::pending()){s_restart=false;run_turbo_phase();continue;}
        static uint16_t seen_freq = 0;"""
replacement = """        // On a Gamma the only AUTO engine is FASTSEARCH. In particular, a
        // network trip must NEVER fall through into the old seven-minute
        // stock climb/trim/watch loop. Explicit fixed-clock mode is separate.
        static bool gamma_search_started = false;
        static unsigned gamma_network_retries = 0;
        static TickType_t gamma_network_failure_tick = 0;
        if(turbo::pending()){
            gamma_search_started = true;
            s_restart = false;
            run_turbo_phase();
            // Only a transient pool/network failure can receive a bounded
            // automatic retry. No auto retry on overcurrent, overheating,
            // sensor, PSU, PLL, error drift or explicit user stop.
            if(turbo::supported() && cfg.autotune && turbo::unlocked() &&
               turbo::reason()==turbo::Reason::Network && gamma_network_retries<2) {
                ++gamma_network_retries;
                gamma_network_failure_tick = xTaskGetTickCount();
            } else {
                gamma_network_failure_tick = 0;
            }
            continue;
        }
        if(turbo::supported() && cfg.autotune){
            // Old stock tuning may leave a seed with excessive hardware errors.
            // Without the stock tuner, recover ONCE to the conservative 525 MHz
            // starting point so the guarded FASTSEARCH preflight can pass.
            static bool gamma_seed_recovered = false;
            if(!gamma_seed_recovered && !gamma_search_started &&
               turbo::unlocked() && board::is_powered() &&
               g_state.hash_counter_ms.load() && g_state.error_pct >= 1.0f){
                gamma_seed_recovered = true;
                if(board::freq_mhz()>525){
                    note("FASTSEARCH: recovering unstable seed at stock clock");
                    if(!apply(525,1150,true))board::shutdown();
                    miner::reset_window();
                }
                vTaskDelay(pdMS_TO_TICKS(30000));
                continue;
            }
            const bool first = !gamma_search_started;
            const bool retry_network = gamma_network_failure_tick!=0 &&
                (TickType_t)(xTaskGetTickCount()-gamma_network_failure_tick)>=pdMS_TO_TICKS(120000);
            // Turbo's request_search() still enforces fresh sensor, PSU,
            // stratum single-active-pool and benchmark/offset safety checks.
            if(turbo::unlocked() && (first || retry_network) &&
               board::is_powered() && g_state.pool_connected && g_state.time_synced &&
               turbo::request_search()) {
                gamma_search_started = true;
                gamma_network_failure_tick = 0;
                g_state.tuner.phase = TunerPhase::WarmUp;
                note("FASTSEARCH: waiting for guarded start");
                continue;
            }
            // Ended search = safe fixed anchor/previous verified rollback,
            // NOT a second automatic search. No unsafe restore of stale 838 MHz.
            if(g_state.tuner.phase != TunerPhase::Off){
                g_state.tuner.phase = TunerPhase::Off;
                note("FASTSEARCH paused; use Retune to restart");
            }
            vTaskDelay(pdMS_TO_TICKS(2000));
            continue;
        }
        static uint16_t seen_freq = 0;"""
s = change_once(s, original, replacement, "exclusive Gamma controller")
s = change_once(s,
    '"TURBO held %u MHz @ %u mV; explicit stop returns stock"',
    '"FASTSEARCH held %u MHz @ %u mV; safety watchdog active"',
    "hold UI explanation")
s = change_once(s,
    """void start()
{
    if (xTaskCreate(tuner_task, "tuner", 4096, NULL, 4, NULL) != pdPASS)""",
    """void start()
{
    // Migrate the stale stock autotune lock without erasing FASTSEARCH's
    // separately validated point archive or overclock/PSU preferences.
    if(turbo::supported() && settings::get().autotune &&
       (settings::get().tuned_freq || settings::get().tuned_mv)){
        settings::get().tuned_freq = settings::get().tuned_mv = 0;
        settings::save();
    }
    if (xTaskCreate(tuner_task, "tuner", 4096, NULL, 4, NULL) != pdPASS)""",
    "drop stored stock autotune lock")
p.write_text(s)

# Stop advertising that an explicit FASTSEARCH cancellation starts another tuner.
for base in (up / "main", root / "overlay/main"):
    p = base / "core/turbo.cpp"
    s = p.read_text()
    s = change_once(s,
        '"Stopping in stock tuner"',
        '"FASTSEARCH stopping; stock autotune is disabled"',
        str(p))
    p.write_text(s)

# New version in binary, fixture and verifier; preserve all checksum tests.
old_version = "1.4.10-hunter-T1000-FASTSEARCH"
new_version = "1.4.10-hunter-T1000-ONE-TUNER"
for name in ("verify_image.py", "tests/image.py"):
    p = root / name
    s = p.read_text()
    assert old_version in s, name
    p.write_text(s.replace(old_version, new_version))
(up / "version.txt").write_text(new_version + "\n")

# Structural guard: ensures the supported-Gamma auto branch ends in
# continue before entering the pre-existing stock climb section.
p = up / "main/core/tuner.cpp"
s = p.read_text()
a = s.index("if(turbo::supported() && cfg.autotune){")
b = s.index("        static uint16_t seen_freq = 0;", a)
fragment = s[a:b]
assert "vTaskDelay(pdMS_TO_TICKS(2000));" in fragment
assert fragment.rstrip().endswith("continue;\n        }")
assert "turbo::reason()==turbo::Reason::Network" in s
assert "gamma_network_retries<2" in s
assert "turbo::request_search()" in fragment
assert "g_state.pool_connected" in fragment
assert "gamma_network_failure_tick" in fragment
print("ONE-TUNER: Gamma uses only guarded FASTSEARCH automation; bounded network retry; stock tuning never reached.")
