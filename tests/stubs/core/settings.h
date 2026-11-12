#pragma once
#include <stdint.h>
enum class PoolMode:uint8_t{Split,Failover};
struct Settings{PoolMode pool_mode;uint16_t job_ms;uint32_t vr_hz;bool autotune;uint8_t tune_goal;uint16_t power_cap_w;};namespace settings{Settings&get();}
