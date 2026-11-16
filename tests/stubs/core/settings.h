#pragma once
#include <stdint.h>
enum class PoolMode:uint8_t{Split,Failover};
struct Settings{PoolMode pool_mode;uint16_t job_ms;uint32_t vr_hz;bool autotune;uint8_t tune_goal;uint16_t power_cap_w;uint16_t freq_mhz=786,core_mv=1170;bool chip_tune=false;int8_t chip_off[1]={};bool overclock=false;uint16_t tuned_freq=0,tuned_mv=0;};namespace settings{Settings&get();void save();}
