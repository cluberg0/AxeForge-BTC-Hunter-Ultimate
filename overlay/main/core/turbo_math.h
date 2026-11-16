#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace turbo_math {
constexpr unsigned MapSize=16;
struct Point{uint16_t mhz=0,mv=0;float watts=0,ghs=0,useful_ghs=0;uint32_t time=0;uint16_t cap=0,replies=0;float max_asic=0,max_vr=0,min_vin=0;};
inline bool valid(const Point&p){return p.mhz>=100&&p.mhz<=1000&&p.mv>=1000&&p.mv<=1300&&std::isfinite(p.watts)&&p.watts>0&&p.watts<=30&&std::isfinite(p.ghs)&&p.ghs>0&&p.ghs<=4000&&std::isfinite(p.useful_ghs)&&p.useful_ghs>=0&&p.cap>=18&&p.cap<=30&&std::isfinite(p.max_asic)&&p.max_asic>0&&p.max_asic<65&&std::isfinite(p.max_vr)&&p.max_vr>0&&p.max_vr<75&&std::isfinite(p.min_vin)&&p.min_vin>=4.85f&&p.min_vin<=5.35f&&p.time>=1577836800u&&p.time<4102444800u;}
struct Budget{float user=0,nominal=0,reserve=0,margin=0,current_limit=0,effective=0;const char*reason="invalid_psu";};
inline bool psu_valid(float watts,float amps){return std::isfinite(watts)&&watts>=15&&watts<=120&&std::isfinite(amps)&&amps>=3&&amps<=24;}
inline Budget budget(float user,float watts,float amps,float vin,float chip,float vr,bool psu_ok){
 Budget b;b.user=user;
 if(!std::isfinite(user)||user<0||user>30||!psu_valid(watts,amps))return b;
 b.nominal=std::min(watts,5.f*amps);b.reserve=std::max(2.f,b.nominal*.10f);b.margin=1.5f; // TPS Pout+board allowance, residual input uncertainty
 b.current_limit=std::min(amps-.5f,6.5f); // reserve from declared supply; software experimental ceiling, not a board rating
 float volts=std::isfinite(vin)&&vin>=4.85f?std::min(vin,5.f):4.85f;
 float supply=b.nominal-b.reserve-b.margin,current=volts*b.current_limit-b.margin;
 b.effective=std::max(0.f,std::min(user,std::min(supply,current)));
 b.reason=b.effective>=user?"user_limit":current<supply?"psu_current_reserve_and_input_uncertainty":"psu_power_reserve_and_input_uncertainty";
 if(!psu_ok||!std::isfinite(vin)||vin<4.95f||chip>=62||vr>=70){b.effective*=.9f;b.reason=!psu_ok?"psu_not_verified":vin<4.95f?"voltage_sag":"thermal_headroom";}
 return b;
}
inline bool max_valid(unsigned f,unsigned cap){return f>=800&&f<=1000&&cap>=18&&cap<=30;}
}
