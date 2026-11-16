#!/usr/bin/env python3
"""Gamma software experiment limits; never claim a measured hardware envelope."""
import pathlib,sys
r=pathlib.Path(sys.argv[1])
def patch(name,a,b):
 p=r/name;s=p.read_text();assert s.count(a)==1,(name,a[:65],s.count(a));p.write_text(s.replace(a,b))
with(r/'boards/gamma.toml').open('a')as f:f.write('\n# Software research ceiling; not a physically validated board envelope.\n[experimental]\nfreq_mhz = 1000\nuser_power_w = 30\n')
patch('tools/gen_board.py','    ("envelope", "freq_mhz", "AF_ENV_FREQ_MHZ"),','    ("envelope", "freq_mhz", "AF_ENV_FREQ_MHZ"),\n    ("experimental", "freq_mhz", "AF_EXPERIMENT_FREQ_MHZ"),\n    ("experimental", "user_power_w", "AF_EXPERIMENT_POWER_W"),')
patch('main/core/gates.cpp','return has_env() && !board::is_rev7();','return (turbo::supported() || has_env()) && !board::is_rev7();')
patch('main/core/gates.cpp','uint16_t env_freq() { return available() ? AF_ENV_FREQ_MHZ : 0; }','uint16_t env_freq() { return turbo::supported()?200:(available()?AF_ENV_FREQ_MHZ:0); }')
patch('main/core/gates.cpp','return turbo::active()?turbo::max_frequency():stock_max_freq() + (active() ? env_freq() : 0);','return turbo::supported()?(active()?1000:800):stock_max_freq() + (active()?env_freq():0);')
patch('main/core/gates.cpp','if(turbo::active() && mv>1300)','if(turbo::supported() && mv>1300)')
# Stock hard board power stays untouched. User limits are separate in the API/tuner.
patch('main/net/web.cpp','''    cJSON *manual_f=cJSON_GetObjectItem(j,"freq");
    if(cJSON_IsNumber(manual_f) && manual_f->valuedouble>800){cJSON_Delete(j);return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Above800MHz only through explicit TURBO session");}''','''    bool proposed_unlock=get_bool(j,"overclock",settings::get().overclock);
    if(proposed_unlock&&!settings::get().overclock){char confirm[16]="";copy_str(j,"confirm",confirm,sizeof(confirm));if(strcmp(confirm,"OVERCLOCK")||!gates::available()){cJSON_Delete(j);return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Type OVERCLOCK; supported Gamma required");}}
    cJSON *manual_f=cJSON_GetObjectItem(j,"freq"),*manual_mv=cJSON_GetObjectItem(j,"mv");float actual=0;
    if((manual_f&&(!cJSON_IsNumber(manual_f)||!std::isfinite(manual_f->valuedouble)||manual_f->valuedouble!=floor(manual_f->valuedouble)||manual_f->valuedouble<100||manual_f->valuedouble>(proposed_unlock?1000:800))) || (manual_mv&&(!cJSON_IsNumber(manual_mv)||!std::isfinite(manual_mv->valuedouble)||manual_mv->valuedouble<1000||manual_mv->valuedouble>1300))){cJSON_Delete(j);return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Frequency/voltage exceeds active mode");}
    if(manual_f&&manual_f->valuedouble>800&&(!settings::get().overclock||!asic::pll_supported(manual_f->valuedouble,actual)||!turbo::manual_check(cJSON_IsNumber(cJSON_GetObjectItem(j,"pcap"))?cJSON_GetObjectItem(j,"pcap")->valuedouble:-1))){cJSON_Delete(j);return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Unlock first; fresh healthy power/PLL required");}''')
patch('main/net/web.cpp','requested_cap->valuedouble>25','requested_cap->valuedouble>(proposed_unlock?30:25)')
patch('main/net/web.cpp','"TURBO blocked: 30W hardware envelope not validated; maximum tuning cap25W"','"User power cap exceeds mode: stock25W, unlocked30W"')
# Existing typed confirmation is validated before any settings mutation. Existing NVS key persists it.
patch('main/net/web.cpp','    c.overclock = oc;','''    c.overclock = oc;
    if(oc_changed&&!oc){c.freq_mhz=525;c.core_mv=1150;c.tuned_freq=c.tuned_mv=0;c.power_cap_w=c.power_cap_w>25?25:c.power_cap_w;}''')
# Enabling changes permissions only. Explicit search buttons queue the same tuner phase.
patch('main/net/web.cpp','|| chip_tune != c.chip_tune || oc_changed;','|| chip_tune != c.chip_tune || (oc_changed&&!oc);')
patch('main/net/web.cpp','''    settings::get().autotune = true;
    settings::save();
    tuner::restart();''','''    if(turbo::unlocked()){
        if(!turbo::request_search())return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Need stable stock point, sufficient accepted work, fresh sensors and no active experiment");
        return httpd_resp_sendstr(req,"Extended search queued in stock tuner");
    }
    settings::get().autotune = true;
    settings::save();
    tuner::restart();''')
patch('main/net/web.cpp','    cJSON_AddNumberToObject(lim, "maxPower", gates::max_power());','''    cJSON_AddNumberToObject(lim, "maxPower", turbo::unlocked()?30:25);
    cJSON_AddNumberToObject(lim, "boardMaxPower", gates::stock_max_power());
    cJSON_AddNumberToObject(lim, "effectivePower", turbo::power_budget());''')
# Allow tuning settings/stop while engaged only after ending search through explicit stop. Restart search remains exclusive.
patch('main/core/tuner.cpp','    if(turbo::active())return fminf(lim,turbo::power_budget());','    if(turbo::unlocked())return fminf(lim,turbo::power_budget());')
# Normal tuner remains stock unless an extended experiment is explicitly queued.
patch('main/core/tuner.cpp','next > gates::max_freq()', 'next > (turbo::active()?gates::max_freq():800)')
patch('main/core/tuner.cpp','''        if (!cfg.autotune) {
            uint16_t want''','''        if (!cfg.autotune) {
            if(turbo::unlocked()&&(cfg.freq_mhz>800||board::freq_mhz()>800)&&!turbo::manual_check()){
                cfg.freq_mhz=525;cfg.core_mv=1150;cfg.tuned_freq=cfg.tuned_mv=0;settings::save();
            }
            uint16_t want''')
patch('main/core/tuner.cpp','if(turbo::active()&&freq!=board::freq_mhz())turbo::changing();','if(turbo::unlocked()&&freq!=board::freq_mhz())turbo::changing();')
patch('main/core/tuner.cpp','                apply(cfg.freq_mhz, cfg.core_mv);','                if(!apply(cfg.freq_mhz,cfg.core_mv)){cfg.freq_mhz=525;cfg.core_mv=1150;cfg.tuned_freq=cfg.tuned_mv=0;settings::save();if(!apply(525,1150,true))board::shutdown();}')
patch('main/net/web.cpp','    if (retune && c.autotune) tuner::restart();','    if(retune&&c.autotune){if(turbo::unlocked())turbo::request_search();else tuner::restart();}')
patch('main/core/tuner.cpp','    if(turbo::unlocked())return fminf(lim,turbo::power_budget());','    if(turbo::active())return fminf(lim,turbo::power_budget());\n    if(turbo::unlocked())lim=fminf(lim,turbo::power_budget());')
patch('main/core/tuner.cpp','    lim = fminf(lim,25.0f);','    if(!turbo::unlocked())lim = fminf(lim,25.0f);')
patch('main/core/monitor.cpp','    // whatever else was pending belongs to the power-up being cut now','    if(turbo::unlocked())turbo::disarm(turbo::Reason::Supply); // stock point before any Safe Recovery retry\n    // whatever else was pending belongs to the power-up being cut now')
patch('main/net/web.cpp','    c.power_cap_w = (uint16_t) cap;','    c.power_cap_w = (uint16_t) cap;\n    turbo::sync_cap(c.power_cap_w);')
patch('main/core/tuner.cpp','    const float p_ceil = power_ceiling();','    float p_ceil = power_ceiling();')
patch('main/core/tuner.cpp','        vTaskDelay(pdMS_TO_TICKS(1000));\n        if ((turbo::active()','        vTaskDelay(pdMS_TO_TICKS(1000));\n        p_ceil=power_ceiling(); // live user/PSU/thermal derating, not a frozen 10-minute budget\n        if ((turbo::active()')
# Every return records the actual attempted measurement, including aborted/error windows.
p=r/'main/core/tuner.cpp';s=p.read_text();a=s.index('static Result measure(');b=s.index('static void lock_point',a);part=s[a:b];part=part.replace('return r;','if(turbo::active())turbo::trial(board::freq_mhz(),board::core_mv(),r.ghs,r.pmax,unsigned(r.verdict));\n            return r;');s=s[:a]+part+s[b:];p.write_text(s)
helper=(pathlib.Path(__file__).resolve().parent/'turbo_confirm.inc').read_text()
patch('main/core/tuner.cpp','// Phase 1: climb.',helper+'\n// Phase 1: climb.')
patch('main/core/tuner.cpp','''        if (r.verdict == Verdict::Stable) {
            float jth''','''        if (r.verdict == Verdict::Stable) {
            if(turbo::active()&&!turbo_confirm(r,f,mv))return false;
            float jth''')
patch('main/core/tuner.cpp','bool better = turbo::active() || (eff_goal','bool better = turbo::active()?turbo::better(r.ghs,mv):(eff_goal')
(r/'version.txt').write_text('1.4.10-hunter-TURBO1000-UNLOCK\n')
print('UNLOCK: persistent stock/extended gates, PSU-derived budget, one tuner, actual PLL and confirmed useful-work ranking')

import subprocess
subprocess.run([sys.executable,str(pathlib.Path(__file__).resolve().parent/"unlock_api.py"),str(r)],check=True)
