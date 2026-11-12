#include "core/intel_math.h"
#include <cassert>
#include <iostream>
using namespace intelligence;
int main(){
 assert(hash_ok(1550)&&hash_ok(0)&&!hash_ok(3933240)&&!hash_ok(NAN)&&!hash_ok(-1));
 float v[N];for(auto &x:v)x=NAN;v[0]=1530;v[1]=55.2;v[3]=23.3;v[10]=1.164;v[11]=148364561003867.0;v[12]=15.2;
 Aggregate a;a.add(100,v);v[0]=NAN;a.add(100,v);auto r=a.finish();assert(r.n==2&&r.time==100&&decode(r.x[0],0)==1530&&std::abs(decode(r.x[10],10)-1.164)<.001);assert(std::isnan(decode(r.x[2],2))&&r.diff>1e14);
 a.add(200,v);assert(a.n==1&&a.bucket==200&&a.finish().x[0]==Missing);
 uint8_t c[]={50,55,75,100};assert(curve_ok(c));assert(curve_floor(40,40,c)==50);assert(curve_floor(55,65,c)==65);assert(curve_floor(50,80,c)==100);assert(curve_floor(NAN,50,c)==100);assert(curve_floor(65,60,c)>=80);uint8_t bad[]={50,70,60,100};assert(!curve_ok(bad));
 Point p{750,1160,25,1470,1790000000};assert(valid_point(p)&&fallback(p,786,1170,774,25));assert(!fallback(p,740,1170,728,25));assert(!fallback(p,786,1150,774,25));assert(!fallback(p,786,1170,774,30));assert(!fallback(p,786,1170,740,25));p.mhz=900;assert(!valid_point(p));
 std::cout<<"PASS: invalid hashrate, aggregates, missing values, precision, curve, sensor failure, safe fallback\n";
}
