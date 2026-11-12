#pragma once
#include <stdint.h>
#include "esp_http_server.h"
namespace hunter {
void start();
void job_sent(int pool,uint32_t generation,int64_t received_us,bool clean);
// V1 request ledger: records difficulty of the submitted job, not current vardiff.
void submitted(int pool,uint32_t id,double difficulty,bool candidate,const char *hash,bool btc_network);
void sent(int pool,uint32_t id,bool ok);
// matched=false for unknown or duplicate replies; callers must skip all legacy counters.
double reply(int pool,uint32_t id,bool ok,bool *matched=nullptr);
void disconnected(int pool);
// SV2 success is aggregated; do not claim individual acceptance.
void sv2_candidate(int pool,const char *hash,bool sent,bool btc_network);
void unavailable_candidate(int pool,const char *hash,bool btc_network);
// Last local candidate recorded on a known BTC host; never sends/replays work.
bool candidate_snapshot(char hash[65],int &pool);
uint16_t interval(uint16_t configured);
esp_err_t get(httpd_req_t*);
esp_err_t set(httpd_req_t*);
}
