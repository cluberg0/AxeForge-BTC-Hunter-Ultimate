#!/usr/bin/env python3
"""Repair NVS diagnostics, transactional retries and confirmed result recovery."""
from pathlib import Path
import json
import sys

root = Path(sys.argv[1])

def replace_once(s, old, new):
    assert s.count(old) == 1, (old[:100], s.count(old))
    return s.replace(old, new, 1)

for base in (root / 'upstream/main', root / 'overlay/main'):
    p = base / 'core/turbo.cpp'
    s = p.read_text()
    s = '#include "esp_log.h"\n#include <algorithm>\n' + s
    a = s.index('bool save(){')
    b = s.index('\n}\n}', a) + 2
    s = s[:a] + '''std::atomic<int> storage_error{ESP_OK};
std::atomic<bool> storage_dirty{false};
uint32_t storage_attempt_ms=0;
bool save(){
 Guard guard;if(!guard.ok){persisted=false;storage_dirty=true;storage_error=ESP_ERR_TIMEOUT;return false;}
 // A ~700-byte archive needs a few dozen entries, not 128 spare entries
 // in addition to its payload. NVS performs its own allocation/compaction.
 // Never erase NVS or any user namespace to recover a diagnostic map.
 esp_err_t e=ESP_FAIL;
 for(unsigned attempt=0;attempt<2;++attempt){
  nvs_handle_t h=0;
  e=nvs_open("af_turbo",NVS_READWRITE,&h);
  if(e!=ESP_OK){ESP_LOGE("turbo","NVS open: %s",esp_err_to_name(e));continue;}
  e=nvs_set_blob(h,"map",&archive,sizeof(archive));
  if(e!=ESP_OK)ESP_LOGE("turbo","NVS map write (%u bytes): %s",unsigned(sizeof(archive)),esp_err_to_name(e));
  else {e=nvs_commit(h);if(e!=ESP_OK)ESP_LOGE("turbo","NVS map commit: %s",esp_err_to_name(e));}
  nvs_close(h);
  if(e==ESP_OK)break;
 }
 storage_attempt_ms=uint32_t(esp_timer_get_time()/1000);
 storage_error=int(e);persisted=e==ESP_OK;storage_dirty=e!=ESP_OK;
 return e==ESP_OK;
}
void retry_storage(){
 // Run in the tuner task, after its health checks, never in the safety monitor.
 // Bound flash wear and keep a failed measurement available in RAM meanwhile.
 if(storage_dirty.load()&&uint32_t(esp_timer_get_time()/1000)-storage_attempt_ms>=60000)save();
}''' + s[b:]
    a = s.index('void start(){')
    b = s.index('\nbool manual_check(', a)
    s = s[:a] + '''void start(){
 mu=xSemaphoreCreateMutex();if(!mu)return;
 nvs_handle_t h=0;esp_err_t e=nvs_open("af_turbo",NVS_READONLY,&h);
 archive=Archive{};confirmed_point=Point{};storage_dirty=false;persisted=true;storage_error=ESP_OK;
 if(e==ESP_OK){
  Archive loaded;size_t n=sizeof(loaded);e=nvs_get_blob(h,"map",&loaded,&n);
  if(e==ESP_OK&&n==sizeof(loaded)&&loaded.magic==archive.magic){
   archive=loaded;for(auto&p:archive.points)if(!turbo_math::valid(p))p=Point{};
  }else if(e!=ESP_ERR_NVS_NOT_FOUND){
   storage_error=e==ESP_OK?ESP_ERR_INVALID_STATE:e;persisted=false;
   ESP_LOGE("turbo","NVS map read (%u bytes): %s",unsigned(n),esp_err_to_name(storage_error.load()));
  }
  Config c;n=sizeof(c);e=nvs_get_blob(h,"config",&c,&n);
  if(e==ESP_OK&&n==sizeof(c)&&c.magic==config.magic&&turbo_math::psu_valid(c.watts,c.amps)&&turbo_math::max_valid(c.maximum,c.cap))config=c;
  else if(e!=ESP_ERR_NVS_NOT_FOUND){
   settings::get().overclock=false;storage_error=e==ESP_OK?ESP_ERR_INVALID_STATE:e;persisted=false;why=Reason::Storage;
   ESP_LOGE("turbo","NVS config read: %s",esp_err_to_name(storage_error.load()));
  }
  nvs_close(h);
 }else if(e!=ESP_ERR_NVS_NOT_FOUND){
  storage_error=e;persisted=false;ESP_LOGE("turbo","NVS read open: %s",esp_err_to_name(e));
 }
 psu_watts=config.watts;psu_amps=config.amps;limit=config.maximum;requested_cap=config.cap;sync_cap(settings::get().power_cap_w);safe_boot();
 // Recover measured results for display. Hardware always follows safe_boot()
 // and guarded remeasurement; neither a saved point nor a probe sets its PLL.
 for(const auto&p:archive.points)if(turbo_math::valid(p)&&p.mhz<=limit.load()&&p.watts<=requested_cap.load()&&
   (p.ghs>confirmed_point.ghs||(p.ghs==confirmed_point.ghs&&p.mv<confirmed_point.mv)))confirmed_point=p;
 best_f=confirmed_point.mhz;best_mv=confirmed_point.mv;best_score=confirmed_point.ghs;best_watts=confirmed_point.watts;
}''' + s[b:]
    old = 'persisted=save();if(!persisted){stop(Reason::Storage);return false;}return true;'
    new = '''storage_dirty=true;persisted=false;
 if(!save())ESP_LOGW("turbo","NVS save failed; verified point remains volatile and mining continues");
 return true;'''
    s = replace_once(s, old, new)
    s = replace_once(s, ' else over_power=0;\n return true;\n}', ' else over_power=0;\n retry_storage();\n return true;\n}') if ' else over_power=0;\n return true;\n}' in s else replace_once(s, '}else over_power=0;\n return true;\n}', '}else over_power=0;\n retry_storage();\n return true;\n}')
    # Diagnostics are real ESP errors, separate from the hardware stop reason.
    old = 'persisted.load()?"true":"false");'
    new = '''persisted.load()?"true":"false");
 n+=snprintf(b+n,12288-size_t(n),",\\\"storageError\\\":%d,\\\"storageDirty\\\":%s",storage_error.load(),storage_dirty.load()?"true":"false");'''
    s = replace_once(s, old, new)
    s = replace_once(s, 'Archive copy;{Guard g;', 'Point confirmed;Archive copy;{Guard g;')
    s = replace_once(s, 'copy=archive;}', 'copy=archive;confirmed=confirmed_point;}')
    s = replace_once(s, 'best_f.load(),best_mv.load(),double(best_score.load()),double(best_watts.load())',
                     'unsigned(confirmed.mhz),unsigned(confirmed.mv),double(confirmed.ghs),double(confirmed.watts)')
    old = 'nvs_handle_t h;if(nvs_open("af_turbo",NVS_READWRITE,&h)!=ESP_OK)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"storage unavailable");bool saved=nvs_set_blob(h,"config",&c,sizeof(c))==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);if(!saved)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"storage failed");'
    new = 'nvs_handle_t h;esp_err_t e=nvs_open("af_turbo",NVS_READWRITE,&h);if(e!=ESP_OK){storage_error=e;ESP_LOGE("turbo","NVS config open: %s",esp_err_to_name(e));return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"storage unavailable");}e=nvs_set_blob(h,"config",&c,sizeof(c));if(e==ESP_OK)e=nvs_commit(h);nvs_close(h);storage_error=e;if(e!=ESP_OK){ESP_LOGE("turbo","NVS config write/commit: %s",esp_err_to_name(e));return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"storage failed");}'
    s = replace_once(s, old, new)
    p.write_text(s)

# Keep strict native API contracts synchronized with the actual firmware.
for p in (root / 'overlay/docs/native-api.json', root / 'upstream/docs/native-api.json'):
    doc = json.loads(p.read_text())
    def extend(obj):
        if isinstance(obj, dict):
            props = obj.get('properties', {})
            if 'persisted' in props and 'points' in props:
                props['storageError'] = {'type': 'integer'}
                props['storageDirty'] = {'type': 'boolean'}
                if 'required' in obj:
                    obj['required'] = list(dict.fromkeys(obj['required'] + ['storageError', 'storageDirty']))
            for value in obj.values():
                extend(value)
        elif isinstance(obj, list):
            for value in obj:
                extend(value)
    extend(doc)
    p.write_text(json.dumps(doc, indent=2) + '\n')

# Existing host tests include overlay turbo.cpp: fault-inject the real code.
p = root / 'tests/stubs/nvs.h'
s = p.read_text() + '\nconstexpr int ESP_ERR_NVS_NOT_FOUND=0x1102, ESP_ERR_INVALID_STATE=0x103, ESP_ERR_TIMEOUT=0x107;\n'
p.write_text(s)
p = root / 'tests/stubs/esp_log.h'
s = p.read_text()
if 'ESP_LOGW' not in s:
    s += '\n#define ESP_LOGW(...) ((void)0)\n'
p.write_text(s)
p = root / 'tests/turbo.cpp'
s = p.read_text()
s = replace_once(s, 'static size_t free_nvs=1000;', 'static size_t free_nvs=1000;static int open_fail=0,set_fail=0,commit_fail=0;static unsigned commits=0;static std::map<std::string,std::vector<unsigned char>> pending_nvs;')
s = replace_once(s, 'int nvs_open(const char*ns,int,nvs_handle_t*h){assert(!strcmp(ns,"af_turbo"));*h=1;return ESP_OK;}', 'int nvs_open(const char*ns,int,nvs_handle_t*h){assert(!strcmp(ns,"af_turbo"));if(open_fail){--open_fail;return ESP_FAIL;}*h=1;pending_nvs.clear();return ESP_OK;}')
s = replace_once(s, 'auto&v=saved[k];if(*n!=v.size())return ESP_FAIL;', 'auto it=saved.find(k);if(it==saved.end())return ESP_ERR_NVS_NOT_FOUND;auto&v=it->second;if(*n!=v.size())return ESP_FAIL;')
s = replace_once(s, 'nvs_writes++;if(write_fail)return ESP_FAIL;auto*a=(const unsigned char*)p;saved[k]={a,a+n};return ESP_OK;', 'nvs_writes++;if(write_fail)return ESP_FAIL;if(set_fail){--set_fail;return ESP_FAIL;}auto*a=(const unsigned char*)p;pending_nvs[k]={a,a+n};return ESP_OK;')
s = replace_once(s, 'int nvs_commit(nvs_handle_t){return write_fail?ESP_FAIL:ESP_OK;}', 'int nvs_commit(nvs_handle_t){++commits;if(write_fail)return ESP_FAIL;if(commit_fail){--commit_fail;return ESP_FAIL;}for(const auto&v:pending_nvs)saved[v.first]=v.second;return ESP_OK;}')
s = replace_once(s, 'free_nvs=128;assert(!turbo::remember(825,1170,1650,24)&&turbo::reason()==turbo::Reason::Storage);', '''free_nvs=0;assert(turbo::remember(825,1170,1650,24)&&turbo::persisted&&turbo::reason()==turbo::Reason::None);
 // Allocation belongs to NVS: a healthy write succeeds despite low global stats.
 for(int failure=0;failure<3;++failure){
  reset();begin();unsigned before=nvs_writes, prior_commits=commits;
  if(failure==0)open_fail=2;else if(failure==1)set_fail=2;else commit_fail=2;
  assert(turbo::remember(850,1220,1681,25));
  assert(!turbo::persisted&&turbo::storage_dirty&&turbo::storage_error==ESP_FAIL&&!turbo::cancelled()&&turbo::reason()==turbo::Reason::None);
  if(failure==0)assert(nvs_writes==before&&commits==prior_commits);
  if(failure==1)assert(nvs_writes==before+2&&commits==prior_commits);
  if(failure==2)assert(nvs_writes==before+2&&commits==prior_commits+2);
  httpd_req_t r{};assert(turbo::get(&r)==0);auto*j=cJSON_Parse(response.c_str());assert(j);
  assert(cJSON_GetObjectItem(j,"storageError")->valueint==ESP_FAIL&&cJSON_IsFalse(cJSON_GetObjectItem(j,"persisted")));cJSON_Delete(j);
  now_us+=60000000;fresh();assert(turbo::check());
  assert(turbo::persisted&&!turbo::storage_dirty&&turbo::storage_error==ESP_OK);
 }
 // A transient write failure retries once immediately, with a real commit.
 reset();begin();set_fail=1;assert(turbo::remember(850,1220,1681,25)&&turbo::persisted);
 turbo::verified(850,1220,1681,25);turbo::finish();g_state.freq_mhz=900;turbo::last_score=1750;turbo::better(1750,1220);
 assert(turbo::best_f==900);g_state.freq_mhz=786;begin();assert(turbo::best_f==0&&turbo::best_score==0&&turbo::confirmed_point.mhz==850);turbo::finish();
 // Simulated reboot recovers confirmed measurements only, without a clock write.
 turbo::best_f=turbo::best_mv=0;turbo::best_score=0;unsigned clock=g_state.freq_mhz;
 turbo::start();assert(turbo::best_f==850&&turbo::best_mv==1220&&turbo::best_score==1681&&g_state.freq_mhz==clock&&!turbo::engaged());
 reset();begin();''')
p.write_text(s)
print('V3 NVS: real errors, synchronized archive writes, bounded retry, no storage-only mining stop; native fault tests updated')
