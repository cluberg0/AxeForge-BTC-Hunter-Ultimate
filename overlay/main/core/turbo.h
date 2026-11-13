#pragma once
#include <cstdint>
#include "esp_http_server.h"
#include "core/turbo_math.h"
namespace turbo {
using Point=turbo_math::Point;
enum class Reason:uint8_t{None,Frequency,Power,Thermal,Supply,Errors,Network,Pll,User,Settings,Storage,Telemetry,Samples,Controller,Voltage,Hold};
void start();
bool pending();bool active();bool engaged();bool cancelled();
uint16_t max_frequency();float power_budget();
bool begin(Point&anchor);bool check();void changing();void window_begin();bool window_end(float ghs);
bool remember(uint16_t f,uint16_t mv,float ghs,float watts,float chip=-1,float vr=-1);
Point fallback(uint16_t failed,float budget);
void holding(Reason reason);void stop(Reason reason);void finish();Reason reason();
Reason monitor_trip();void disarm(Reason reason);
esp_err_t get(httpd_req_t*);esp_err_t set(httpd_req_t*);
}
