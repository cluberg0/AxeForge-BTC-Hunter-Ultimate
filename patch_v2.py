#!/usr/bin/env python3
"""Final 2.0 integration on top of the validated Ultimate patch chain."""
import pathlib,sys
r=pathlib.Path(sys.argv[1])
def patch(name,old,new):
 p=r/name;s=p.read_text();assert s.count(old)==1,(name,old[:70],s.count(old));p.write_text(s.replace(old,new))
patch('main/net/weather.h','const char *describe(int wmo_code);','const char *describe(int wmo_code);\nint offset_minutes();\nbool set_offset_minutes(int value);')
patch('main/stratum/pools.cpp','#include "core/hunter.h"','#include "core/hunter.h"\n#include "core/net_policy.h"\n#include "core/net_health.h"')
patch('main/stratum/pools.cpp','    StratumJob job;','    esp_transport_keep_alive_t keepalive{true,60,20,3};\n    StratumJob job;')
patch('main/stratum/pools.cpp','    if (cfg.proto == PoolProto::V1Tls) esp_transport_ssl_crt_bundle_attach(p.t, esp_crt_bundle_attach);','    if (cfg.proto == PoolProto::V1Tls) {\n        esp_transport_ssl_crt_bundle_attach(p.t, esp_crt_bundle_attach);\n        esp_transport_ssl_set_keep_alive(p.t, &p.keepalive);\n    } else esp_transport_tcp_set_keep_alive(p.t, &p.keepalive);')
patch('main/stratum/pools.cpp','    if (!root) return;','    if (!root) { net_health::error(p.idx,net_health::Error::Malformed); return; }')
patch('main/stratum/pools.cpp','        int ready = esp_transport_poll_read(p.t, 200);\n        if (ready < 0) break;','        int ready = esp_transport_poll_read(p.t, 200);\n        if (ready < 0) { net_health::error(p.idx,net_health::Error::Read); break; }')
# V1 and SV2 share an idle policy; the active miner still uses the stock180s.
p=r/'main/stratum/pools.cpp';s=p.read_text();old='esp_timer_get_time() - last_rx > IDLE_RECONNECT_S * 1000000LL';assert s.count(old)==2;s=s.replace(old,'net_policy::idle_expired(esp_timer_get_time(),last_rx,net_health::active(p.idx))');s=s.replace('ESP_LOGW(TAG, "[%d] idle too long, reconnecting", p.idx);','net_health::error(p.idx,net_health::Error::Idle);\n                ESP_LOGW(TAG, "[%d] idle too long, reconnecting", p.idx);');p.write_text(s)
patch('main/stratum/pools.cpp','            set_status(p, "Connection closed");\n            break;','            net_health::error(p.idx,net_health::Error::Read);\n            set_status(p, "Connection closed");\n            break;')
patch('main/stratum/pools.cpp','        last_rx = esp_timer_get_time();\n        fill += n;','        last_rx = esp_timer_get_time();\n        net_health::received(p.idx,uint32_t(n));\n        fill += n;')
patch('main/stratum/pools.cpp','            if (nl > start) v1_message(p, start);','            if (nl > start) { int64_t began=esp_timer_get_time(); v1_message(p,start); net_health::processed(p.idx,esp_timer_get_time()-began); }')
patch('main/stratum/pools.cpp','            last_rx = esp_timer_get_time();\n            sv2_parse_frame_header','            last_rx = esp_timer_get_time();\n            net_health::received(p.idx,uint32_t(len+6));\n            sv2_parse_frame_header')
patch('main/stratum/pools.cpp','            v2_message(p, fh.msg_type, buf, len);','            int64_t began=esp_timer_get_time();\n            v2_message(p, fh.msg_type, buf, len);\n            net_health::processed(p.idx,esp_timer_get_time()-began);')
patch('main/stratum/pools.cpp','        if (transport_connect(p, cfg)) {\n            backoff_s = 2;','        net_health::attempt(p.idx);\n        int64_t session_began=esp_timer_get_time();\n        if (transport_connect(p, cfg)) {\n            net_health::connected(p.idx);')
patch('main/stratum/pools.cpp','        ps.connected = false;','        const bool healthy=esp_timer_get_time()-session_began>=300000000LL && p.have_job;\n        net_health::disconnected(p.idx);\n        ps.connected = false;')
patch('main/stratum/pools.cpp','            if (backoff_s < 60) backoff_s *= 2;','            backoff_s=int(net_policy::next_backoff(unsigned(backoff_s),healthy));')
# Keep a stable alternative while a recovered higher-priority pool proves readiness.
patch('main/mining/miner.cpp','#include "core/hunter.h"','#include "core/hunter.h"\n#include "core/net_policy.h"\n#include "core/net_health.h"')
patch('main/mining/miner.cpp','''    if (cfg.pool_mode == PoolMode::Failover) {
        for (int i = 0; i < AF_MAX_POOLS; i++)
            if (ok[i]) return i;
        return -1;
    }''','''    if (cfg.pool_mode == PoolMode::Failover) {
        static net_policy::Failover policy;
        uint32_t sessions[AF_MAX_POOLS];
        for(int i=0;i<AF_MAX_POOLS;i++)sessions[i]=slots[i].info.session;
        return policy.choose(ok,sessions,esp_timer_get_time());
    }''')
patch('main/mining/miner.cpp','        g_state.pool_connected = p >= 0;','        g_state.pool_connected = p >= 0;\n        net_health::selected(p);')
# Disable periodic farm requests, retaining explicit discovery and cached API.
patch('main/net/swarm.cpp','''    while (true) {
        if (wifi::connected() && g_state.ip[0]) {''','''    while (true) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (wifi::connected() && g_state.ip[0]) {''')
patch('main/net/swarm.cpp','        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(POLL_S * 1000));','        // No periodic scanning or polling without an explicit client request.')
patch('main/net/swarm.cpp','char *to_json()\n{','char *to_json()\n{\n    static int64_t last_request=0;\n    int64_t now=esp_timer_get_time();\n    if(s_task && now-last_request>=15000000LL){last_request=now;xTaskNotifyGive(s_task);}')
patch('main/net/swarm.cpp','#include "esp_log.h"','#include "esp_log.h"\n#include "esp_timer.h"')
# A saved auto_update preference must not replace this custom firmware overnight.
patch('main/net/fwupdate.cpp','    int64_t next_s = FIRST_CHECK_S;','    // Updates/checks only on explicit web API request.')
patch('main/net/fwupdate.cpp','        int64_t now_s = esp_timer_get_time() / 1000000;','')
patch('main/net/fwupdate.cpp','        if (s_check_req || now_s >= next_s) {','        if (s_check_req) {')
patch('main/net/fwupdate.cpp','            next_s = now_s + CHECK_EVERY_S;','')
patch('main/net/fwupdate.cpp','    if (!settings::get().auto_update || !s_info.newer) return false;','    // 2.0 never performs unattended external OTA, even with an old saved flag.\n    return false;\n    if (!settings::get().auto_update || !s_info.newer) return false;')
# Add an isolated additive API, under the existing guard. No HTTP handler does networking.
patch('main/net/web.cpp','#include "core/hunter.h"','#include "core/hunter.h"\n#include "core/net_health.h"\n#include <cmath>')
patch('main/net/web.cpp','    cfg.max_uri_handlers = 42;','    cfg.max_uri_handlers = 44;')
patch('main/net/web.cpp','        {"/api/status", HTTP_GET, status_get, NULL},','        {"/api/status", HTTP_GET, status_get, NULL},\n        {"/api/network", HTTP_GET, net_health::get, NULL},\n        {"/api/network", HTTP_POST, net_health::set, NULL},')
(r/'version.txt').write_text('1.4.10-hunter-ultimate-2.0\n')
print('Ultimate 2.0 network/service integration applied')

# Applied after the first2.0 patch stage.
p=r/'main/net/fwupdate.cpp';s=p.read_text();a=s.index('static bool auto_ok()');b=s.index('// Flash writes',a);s=s[:a]+'static bool auto_ok() { return false; } // manual OTA only\n\n'+s[b:];p.write_text(s)
p=r/'main/stratum/pools.cpp';s=p.read_text();s=s.replace('    if (!ok) p.restart = true;','    if (!ok) { net_health::error(p.idx,net_health::Error::Write); p.restart = true; }');s=s.replace('        set_status(p, "Can\'t connect to %s", cfg.url);','        net_health::error(p.idx,net_health::Error::Connect);\n        set_status(p, "Can\'t connect to %s", cfg.url);');s=s.replace('            if (ready < 0) break;','            if (ready < 0) { net_health::error(p.idx,net_health::Error::Read); break; }');s=s.replace('            if (!v2_recv(p, hdr, buf, &len)) {','            if (!v2_recv(p, hdr, buf, &len)) {\n                net_health::error(p.idx,net_health::Error::Read);');p.write_text(s)
patch('main/core/tuner.cpp','    float lim = gates::max_power();','    float lim = gates::max_power();\n#if defined(AF_ASIC_BM1370) && AF_NUM_ASICS == 1\n    // Gamma601: 30W operation has no hardware validation in this release.\n    // Preserve saved configuration, constrain only the stock tuning envelope.\n    lim = fminf(lim,25.0f);\n#endif')
# Reject a new over25W tuning request before mutating any saved settings.
p=r/'main/net/web.cpp';s=p.read_text();a=s.index('static esp_err_t settings_post');b=s.index('\n}',a);part=s[a:b];anchor='    Settings &c = settings::get();';assert part.count(anchor)==1
part=part.replace(anchor,'''#if defined(AF_ASIC_BM1370) && AF_NUM_ASICS == 1
    cJSON *requested_cap = cJSON_GetObjectItem(j,"pcap");
    if (cJSON_IsNumber(requested_cap) && (!std::isfinite(requested_cap->valuedouble) || requested_cap->valuedouble>25 || requested_cap->valuedouble<0)) {
        cJSON_Delete(j);
        return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"TURBO blocked: 30W hardware envelope not validated; maximum tuning cap25W");
    }
#endif
'''+anchor);s=s[:a]+part+s[b:];p.write_text(s)

patch('main/mining/miner.cpp','        g_state.hash_counter_ms.store(0);\n        ESP_LOGW(TAG, "invalid counter rate','        g_state.hash_counter_ms.store(0);\n        s_prev_err_t[chip]=0; // invalid/reset valid counter also invalidates the error baseline\n        ESP_LOGW(TAG, "invalid counter rate')

patch('main/net/web.cpp','    cfg.stack_size = 8192;','    cfg.stack_size = 8192;\n    cfg.task_priority = 3; // below Stratum5 and ASIC result12; monitor priorities unchanged')

patch('main/stratum/pools.cpp','    std::atomic<bool> restart{false};','    std::atomic<bool> restart{false};\n    std::atomic<uint32_t> config_epoch{0};')
patch('main/stratum/pools.cpp','        p.restart = false;\n        PoolCfg cfg','        p.restart = false;\n        const uint32_t config_generation=p.config_epoch.load();\n        PoolCfg cfg')
patch('main/stratum/pools.cpp','        if (!p.restart) {\n            ulTaskNotifyTake','        if (healthy) backoff_s=2;\n        // IO errors also set restart; only a configuration change skips backoff.\n        if (p.config_epoch.load()==config_generation) {\n            ulTaskNotifyTake')
patch('main/stratum/pools.cpp','        p.restart = true;\n        if (p.task) xTaskNotifyGive(p.task);','        p.config_epoch.fetch_add(1);\n        p.restart = true;\n        if (p.task) xTaskNotifyGive(p.task);')

patch('main/net/price.cpp','static void price_task(void *)','[[maybe_unused]] static void price_task(void *)')
patch('main/net/price.cpp','    // PSRAM stack: this task only does HTTP, never flash writes\n    xTaskCreatePinnedToCoreWithCaps(price_task, "price", 8192, NULL, 2, &s_task, tskNO_AFFINITY, MALLOC_CAP_SPIRAM);','    // Manual energy tariffs remain; no market HTTP feed or automatic cost-based pause.\n    s_now=NAN;s_have=false;s_pause=false;\n    snprintf(s_err,sizeof(s_err),"Market polling disabled in Ultimate2.0; use manual tariff");')
