#pragma once
#include <cmath>
#include <cstdint>
#include <algorithm>
namespace intelligence {
constexpr unsigned N=13;
constexpr uint16_t Missing=65535;
inline bool range(float v,float lo,float hi){return std::isfinite(v)&&v>=lo&&v<=hi;}
// GH/s, C, C, W, %, MHz, mV, %, RPM, V, V (core), network difficulty, J/TH.
constexpr float scales[N]={1,10,10,10,10,1,1,100,1,1000,1000,1,10};
inline uint16_t encode(float v,unsigned i){if(i>=N||i==11||!range(v,0,65534.f/scales[i]))return Missing;return uint16_t(std::lround(v*scales[i]));}
inline float decode(uint16_t v,unsigned i){return v==Missing?NAN:float(v)/scales[i];}
inline bool hash_ok(float v){return range(v,0,4000);}
struct Record {uint32_t time=0;float diff=NAN;uint16_t n=0;uint16_t x[N]={};uint32_t step=30;};
struct Aggregate {uint32_t bucket=0;uint16_t n=0;double sum[N]={};uint32_t cnt[N]={};
 void add(uint32_t b,const float *v){if(!bucket||b!=bucket){*this=Aggregate{};bucket=b;}if(n<65534)n++;for(unsigned i=0;i<N;i++)if(std::isfinite(v[i])){sum[i]+=v[i];cnt[i]++;}}
 Record finish(uint32_t step=30) const {Record r;r.step=step;r.time=bucket;r.n=n;for(unsigned i=0;i<N;i++)r.x[i]=cnt[i]?encode(float(sum[i]/cnt[i]),i):Missing;r.diff=cnt[11]?float(sum[11]/cnt[11]):NAN;return r;}
};
struct Point {uint16_t mhz=0,mv=0,cap=0;uint16_t ghs=0;uint32_t time=0;};
inline bool same_point(const Point&a,const Point&b){return a.mhz==b.mhz&&a.mv==b.mv&&a.cap==b.cap;}
inline bool valid_point(const Point&p){return p.mhz>=100&&p.mhz<=800&&p.mv>=1000&&p.mv<=1300&&p.cap>0&&p.cap<=30&&p.ghs>0&&p.ghs<=4000;}
inline bool fallback(const Point&p,uint16_t f,uint16_t mv,uint16_t next,uint16_t cap){return valid_point(p)&&p.cap==cap&&p.mhz<f&&p.mhz<=next&&p.mv<=mv;}
inline int curve_floor(float chip,float vr,const uint8_t *c){if(!range(chip,0,110)||!range(vr,0,130))return 100;float t=std::max(chip,vr-10);float x=std::max(0.f,std::min(3.f,(t-40)/10));int i=int(x);float v=i>=3?c[3]:c[i]+(c[i+1]-c[i])*(x-i);if(chip>=65||vr>=75)v=std::max(v,80.f);return std::max(50,std::min(100,int(std::ceil(v))));}
inline bool curve_ok(const uint8_t*c){for(int i=0;i<4;i++)if(c[i]<50||c[i]>100||(i&&c[i]<c[i-1]))return false;return true;}
}
