#!/usr/bin/env python3
from pathlib import Path
import sys
p=Path(sys.argv[1])/"upstream/main/net/web.cpp"
s=p.read_text()
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:80],s.count(a))
 s=s.replace(a,b,1)
patch('if(retune&&c.autotune){if(turbo::unlocked())turbo::request_search();else tuner::restart();}',
 '''if(retune&&c.autotune){
        if(turbo::supported()){if(turbo::unlocked())turbo::request_search();}
        else tuner::restart();
    }''')
patch('''    settings::get().autotune = true;
    settings::save();
    tuner::restart();
    return httpd_resp_sendstr(req, "Auto-tune restarted. A full search takes 1-2 hours.");''',
 '''    if(turbo::supported())return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,
        "Only FASTSEARCH is available on Gamma; unlock it first");
    settings::get().autotune = true;
    settings::save();
    tuner::restart();
    return httpd_resp_sendstr(req, "Auto-tune restarted. A full search takes 1-2 hours.");''')
patch('return httpd_resp_sendstr(req,"Extended search queued in stock tuner");',
      'return httpd_resp_sendstr(req,"FASTSEARCH queued in ONE-TUNER controller");')
patch('    c.chip_tune = chip_tune;',
 '''    c.chip_tune = chip_tune;
    // On supported Gamma only one automatic frequency tuner is allowed.
    if(turbo::supported() && c.overclock){
        c.autotune = true;
        c.tune_goal = 1;
        c.chip_tune = false;
    }''')
p.write_text(s)
assert s.count('tuner::restart()')==2
print("Gamma API cannot enter stock search; FASTSEARCH retains all PSU guards.")
