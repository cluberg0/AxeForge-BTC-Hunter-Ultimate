#pragma once
#include <cstdint>
struct State{bool time_synced=false;struct Weather{bool valid=false;int32_t utc_offset_s=0;char error[128]={};}weather;struct Mempool{bool valid=true;char error[128]={};}mempool;};extern State g_state;
