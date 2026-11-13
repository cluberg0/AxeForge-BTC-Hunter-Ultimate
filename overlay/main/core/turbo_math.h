#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace turbo_math {
constexpr unsigned MapSize=16;
struct Point{uint16_t mhz=0,mv=0;float watts=0,ghs=0,useful_ghs=0;uint32_t time=0;uint16_t cap=0,replies=0;float max_asic=0,max_vr=0,min_vin=0;};
inline bool valid(const Point&p){return p.mhz>=100&&p.mhz<=1000&&p.mv>=1000&&p.mv<=1300&&std::isfinite(p.watts)&&p.watts>0&&p.watts<=30&&std::isfinite(p.ghs)&&p.ghs>0&&p.ghs<=4000&&std::isfinite(p.useful_ghs)&&p.useful_ghs>=0&&p.cap>=18&&p.cap<=30&&std::isfinite(p.max_asic)&&p.max_asic>0&&p.max_asic<65&&std::isfinite(p.max_vr)&&p.max_vr>0&&p.max_vr<75&&std::isfinite(p.min_vin)&&p.min_vin>=4.85f&&p.min_vin<=5.35f&&p.time>=1577836800u&&p.time<4102444800u;}
inline float budget(float requested,bool direct_input,float vin,float chip,float vr,bool psu_ok){
 if(!std::isfinite(requested)||requested<18||requested>30)return 0;
 float p=std::min(27.f,requested-3.f); // 3W for transients/measurement and board/fan uncertainty
 if(!direct_input)p=std::min(p,25.f); // Gamma: TPS546 output+allowance, not calibrated wall input
 if(!psu_ok||vin<4.95f||chip>=62.f||vr>=70.f)p=std::min(p,23.f);
 return p;
}
inline bool max_valid(unsigned f,unsigned cap){return f>=800&&f<=1000&&f%25==0&&cap>=18&&cap<=30;}
}
