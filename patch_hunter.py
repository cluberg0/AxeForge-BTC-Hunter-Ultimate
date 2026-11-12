"""Install BTC Hunter changes on the already pinned/modified upstream tree."""
from pathlib import Path
import sys
R=Path(sys.argv[1])
def patch(name, pairs):
 p=R/name;s=p.read_text()
 for old,new in pairs:
  assert s.count(old)==1,(name,old[:100],s.count(old));s=s.replace(old,new)
 p.write_text(s)
def inc(name):return ('#include "'+name+'"','#include "'+name+'"\n#include "core/hunter.h"')
patch('main/main.cpp',[inc('core/intelligence.h'),('    intel::start();  // low-priority history task; no changes to settings namespace','    intel::start();  // low-priority history task; no changes to settings namespace\n    hunter::start();')])
patch('main/net/web.cpp',[inc('core/intelligence.h'),('    cfg.max_uri_handlers = 38;','    cfg.max_uri_handlers = 40;'),('        {"/api/intelligence", HTTP_POST, intel::set, NULL},','        {"/api/intelligence", HTTP_POST, intel::set, NULL},\n        {"/api/hunter", HTTP_GET, hunter::get, NULL},\n        {"/api/hunter", HTTP_POST, hunter::set, NULL},')])
patch('main/stratum/pools.h', [('    double difficulty;     // the pool\'s share difficulty, fraction included','    double difficulty;     // the pool\'s share difficulty, fraction included\n    int64_t received_us;\n    bool clean;\n    uint32_t session;'),('void submit(int pool, const Work &w, uint32_t nonce, uint32_t version, int chip);','void submit(int pool, const Work &w, uint32_t nonce, uint32_t version, int chip, bool candidate = false, const char *hash = nullptr);')])
patch('main/mining/work.cpp',[('#include "work.h"','#include "work.h"\n#include "core/hunter_math.h"'),('    snprintf(w.extranonce2, sizeof(w.extranonce2), "%0*lx", en2_len * 2, (unsigned long) en2);','    snprintf(w.extranonce2, sizeof(w.extranonce2), "%0*lx", en2_len * 2, (unsigned long) hunter_math::en2_value(en2, en2_len));')])
patch('main/mining/work.h',[('    int pool = 0;','    int pool = 0;\n    uint32_t pool_session = 0;')])
patch('main/stratum/pools.cpp',[inc('core/state.h'),('#include <ctype.h>','#include <ctype.h>\n#include <atomic>'),('    bool clean = false;','    bool clean = false;\n    int64_t received_us = 0;\n    std::atomic<uint32_t> session{1};\n    char session_user[96] = {};'),('    free(p.job.coinb1);\n    free(p.job.coinb2);\n    p.job = j;', '''    // A changed previous hash always makes old work stale, even if the pool omitted clean_jobs.
    if (p.have_job && memcmp(p.job.prev_hash_raw, j.prev_hash_raw, 32)) j.clean = true;
    p.received_us = esp_timer_get_time();
    free(p.job.coinb1);
    free(p.job.coinb2);
    p.job = j;'''),('static void on_share_result(Pool &p, bool ok, const char *err)','static void on_share_result(Pool &p, bool ok, const char *err, double credited = -1)'),('        ps.accepted_work += p.diff;','        const double work_diff = credited >= 0 ? credited : p.diff;\n        ps.accepted_work += work_diff;'),('        p.work_window += p.diff;','        p.work_window += work_diff;'),('            on_share_result(p, cJSON_IsTrue(result), err);','            const double credited = hunter::reply(p.idx, (uint32_t)rid, cJSON_IsTrue(result));\n            on_share_result(p, cJSON_IsTrue(result), err, credited);'),('        ps.connected = false;\n        xSemaphoreTake(p.lock, portMAX_DELAY);','        ps.connected = false;\n        hunter::disconnected(p.idx);\n        xSemaphoreTake(p.lock, portMAX_DELAY);'),('        info.difficulty = p.diff;','        info.difficulty = p.diff;\n        info.received_us = p.received_us;\n        info.clean = p.job.clean || p.clean;\n        info.session = p.session;'),('static void transport_close(Pool &p)\n{\n    xSemaphoreTake(p.io, portMAX_DELAY);','static void transport_close(Pool &p)\n{\n    xSemaphoreTake(p.io, portMAX_DELAY);\n    if (++p.session == 0) p.session = 1;'),('        set_status(p, "Connecting...");','        xSemaphoreTake(p.io, portMAX_DELAY);\n        snprintf(p.session_user, sizeof(p.session_user), "%s", cfg.user);\n        xSemaphoreGive(p.io);\n        set_status(p, "Connecting...");'),('static bool send_line(Pool &p, const char *line)','static bool send_line(Pool &p, const char *line, uint32_t session = 0)'),('    bool ok = p.t && esp_transport_write','    bool ok = (!session || session == p.session) && p.t && esp_transport_write'),('static bool send_frame(Pool &p, const uint8_t *frame, int len)','static bool send_frame(Pool &p, const uint8_t *frame, int len, uint32_t session = 0)'),('    bool ok = p.noise && p.t && sv2_noise_send','    bool ok = (!session || session == p.session) && p.noise && p.t && sv2_noise_send'),('void submit(int i, const Work &w, uint32_t nonce, uint32_t version, int chip)','void submit(int i, const Work &w, uint32_t nonce, uint32_t version, int chip, bool candidate, const char *hash)'),('    if (!g_state.pools[i].connected) return;','    if (!g_state.pools[i].connected || w.pool_session != p.session) { if (candidate) hunter::unavailable_candidate(i, hash); return; }'),('        if (n > 0) send_frame(p, frame, n);\n        return;','        bool ok = n > 0 && send_frame(p, frame, n, w.pool_session);\n        if (candidate) hunter::sv2_candidate(i, hash, ok);\n        return;'),('    char line[340], worker[112];\n    const char *user = settings::get().pools[i].user;','    const uint32_t request_id = p.submit_id++;\n    char line[340], worker[112], session_user[96];\n    xSemaphoreTake(p.io, portMAX_DELAY);\n    memcpy(session_user, p.session_user, sizeof(session_user));\n    xSemaphoreGive(p.io);\n    session_user[sizeof(session_user)-1] = 0;\n    const char *user = session_user;'),('(unsigned long) p.submit_id++, user, w.job_id, w.extranonce2,','(unsigned long) request_id, user, w.job_id, w.extranonce2,'),('    send_line(p, line);\n}\n\n} // namespace pools','    hunter::submitted(i, request_id, w.pool_diff, candidate, hash);\n    hunter::sent(i, request_id, send_line(p, line, w.pool_session));\n}\n\n} // namespace pools')])
patch('main/mining/miner.cpp',[('#include "core/state.h"','#include "core/state.h"\n#include "core/hunter.h"\n#include "core/hunter_math.h"'),('    uint32_t en2 = 0;','    uint32_t en2 = 0;\n    uint64_t en2_used = 0;'),('static int pick_pool(PoolSlot *slots)','''// Ignore job ID and version-only changes: those can represent the same rolled header.
static bool same_header(const PoolSlot &old, const StratumJob &next, const pools::JobInfo &previous, const pools::JobInfo &info)
{
    const auto &a = old.tmpl;
    return old.have && previous.en2_len == info.en2_len && !strcmp(previous.en1, info.en1) &&
           a.coinb1 && a.coinb2 && next.coinb1 && next.coinb2 &&
           !strcmp(a.coinb1, next.coinb1) && !strcmp(a.coinb2, next.coinb2) &&
           a.nbits == next.nbits && a.ntime == next.ntime && a.n_merkle == next.n_merkle &&
           a.n_merkle >= 0 && a.n_merkle <= MAX_MERKLE_BRANCHES &&
           !memcmp(a.prev_hash_raw, next.prev_hash_raw, 32) &&
           !memcmp(a.merkle, next.merkle, (size_t)a.n_merkle * 32);
}
static int pick_pool(PoolSlot *slots)'''),('        ok[i] = slots[i].have && pools::ready(i) && cfg.pools[i].enabled;','        ok[i] = slots[i].have && pools::ready(i) && cfg.pools[i].enabled &&\n                slots[i].en2_used < hunter_math::en2_capacity(slots[i].info.en2_len);'),('            StratumJob next;\n            if (pools::fetch_job(i, next, s.info, &s.gen)) {','            StratumJob next;\n            const pools::JobInfo previous = s.info;\n            if (pools::fetch_job(i, next, s.info, &s.gen)) {\n                if (!same_header(s, next, previous, s.info)) s.en2_used = 0;'),('        w.pool = p;','        w.pool = p;\n        w.pool_session = s.info.session;'),('        g_state.pools[p].jobs++;','        hunter::job_sent(p, s.gen, s.info.received_us, s.info.clean);\n        if (++s.en2_used == hunter_math::en2_capacity(s.info.en2_len))\n            ESP_LOGW(TAG, "pool %d: extranonce2 space exhausted; waiting for fresh header", p + 1);\n        g_state.pools[p].jobs++;'),('        uint16_t job_ms = settings::get().job_ms;','        uint16_t job_ms = hunter::interval(settings::get().job_ms);'),('    portENTER_CRITICAL(&s_win_mux);\n    if (is_error) {','    // Gamma: reject nonphysical valid-count samples before poisoning the EMA or tuner.\n    // The baseline has already been advanced, so a counter reset affects only this sample.\n    if (!is_error && !hunter_math::rate_ok(ghs)) { ESP_LOGW(TAG, "invalid counter rate %.0f GH/s, skipped", ghs); return; }\n    portENTER_CRITICAL(&s_win_mux);\n    if (is_error) {'),('''struct RecentResult {
    uint8_t slot;
    uint32_t nonce, version;
};

static bool seen_before(uint8_t slot, uint32_t nonce, uint32_t version)
{
    static RecentResult recent[RECENT_RESULTS];
    static int next = 0;
    for (const RecentResult &x : recent)
        if (x.slot == slot && x.nonce == nonce && x.version == version) return true;
    recent[next] = {slot, nonce, version};
    next = (next + 1) % RECENT_RESULTS;
    return false;
}''','''struct RecentResult { bool valid = false; int pool = 0; uint8_t hash[32] = {}; };
static bool seen_before(int pool, const uint8_t hash[32])
{
    static RecentResult recent[RECENT_RESULTS];
    static int next = 0;
    for (const RecentResult &x : recent)
        if (x.valid && x.pool == pool && !memcmp(x.hash, hash, 32)) return true;
    recent[next].valid = true; recent[next].pool = pool;
    memcpy(recent[next].hash, hash, 32);
    next = (next + 1) % RECENT_RESULTS;
    return false;
}'''),('        if (seen_before(r.job_slot, r.nonce, version)) {','        double diff = work::nonce_difficulty(w, r.nonce, version, hash);\n        if (seen_before(w.pool, hash)) {'),('        double diff = work::nonce_difficulty(w, r.nonce, version, hash);\n        g_state.hashes_checked++;','        g_state.hashes_checked++;'),('        g_state.hashes_checked++;','''        const bool candidate = hunter_math::meets(hash, w.nbits);
        // A full target hit gets the originating connection first, before logging/statistics.
        if (candidate) {
            char display_hash[65]; uint8_t be_candidate[32];
            for (int i = 0; i < 32; i++) be_candidate[i] = hash[31 - i];
            work::bin2hex(be_candidate, 32, display_hash);
            pools::submit(w.pool, w, r.nonce, version, r.chip, true, display_hash);
        }
        g_state.hashes_checked++;'''),('        if (diff >= w.pool_diff) {','        if (candidate || diff >= w.pool_diff) {'),('''            pools::submit(w.pool, w, r.nonce, version, r.chip);
            if (diff >= work::nbits_to_difficulty(w.nbits)) {
                g_state.blocks_found++;
                ESP_LOGW(TAG, "!!! BLOCK FOUND !!! diff %.0f on pool %d", diff, w.pool);
                notify::post(NOTIFY_BLOCK, "BLOCK FOUND at height %lu, difficulty %.0f, pool %d",
                             (unsigned long) g_state.block_height, diff, w.pool + 1);
            }''','''            // Send the exact-target candidate on its originating pool, even if share difficulty is higher.
            // No flash or notification before the submission; never replay it to another pool.
            if (!candidate) pools::submit(w.pool, w, r.nonce, version, r.chip);
            if (candidate) {
                g_state.blocks_found++;  // local candidates, not chain confirmations
                ESP_LOGW(TAG, "BLOCK CANDIDATE diff %.0f on pool %d (check Hunter reply)", diff, w.pool);
                notify::post(NOTIFY_BLOCK, "BLOCK CANDIDATE pool %d: %s (not confirmed on chain)", w.pool + 1, g_state.last_hash);
            }''')])
print('BTC Hunter hooks applied')
