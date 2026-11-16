#pragma once
#include <cmath>
namespace bm1370_pll {
struct Plan{int ref=0,fb=0,p1=0,p2=0;float actual=0;explicit operator bool()const{return fb!=0;}};
// Same bounded search/tie order as pinned AxeForge BM1370 send_pll.
inline Plan solve(float target){
 Plan q;float diff=2;int product=255,p2min=255;
 if(!std::isfinite(target)||target<=0||target>1000)return q;
 for(int ref=2;ref>0;--ref)for(int p1=7;p1>0;--p1)for(int p2=7;p2>0;--p2){
  int fb=int(std::round(target/25*(ref*p2*p1)));float f=25.f*fb/(ref*p2*p1);
  if(fb>=0xa0&&fb<=0xef&&std::fabs(target-f)<=diff&&p1>=p2&&p1*p2<product&&p2<=p2min){
   q={ref,fb,p1,p2,f};diff=std::fabs(target-f);product=p1*p2;p2min=p2;
  }
 }
 return q;
}
inline unsigned next_point(unsigned current,unsigned maximum){unsigned n=unsigned(std::lround((std::floor(float(current)/12.5f)+1)*12.5f));return n<=maximum&&n<=1000?n:0;}
}
