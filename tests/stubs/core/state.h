#pragma once
#include <cstdint>
enum class SysStatus:uint8_t{Booting,Mining};enum class TunerPhase:uint8_t{Off,Locked};struct TunerState{TunerPhase phase;};
struct PoolState{bool enabled,connected,payout_blocked;uint8_t work_pct,proto;char host[64];};
struct MinerState{PoolState pools[4];SysStatus status;bool temp_ok,vr_temp_ok,time_synced,pool_connected,fan_present[2];float hashrate_ghs,chip_temp_max,vr_temp,pin,error_pct,vin,vout,expected_ghs;uint8_t fan_pct;uint16_t freq_mhz,core_mv,fan_rpm[2];char pool_host[64];uint32_t network_nbits;TunerState tuner;};extern MinerState g_state;
