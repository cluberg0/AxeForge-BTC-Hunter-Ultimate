#pragma once
#include <stdint.h>
#include <cmath>
#include <cstring>
namespace hunter_math {
// Bitcoin compact target, little endian; reject negative/zero/overflow.
inline bool target(uint32_t bits, uint8_t out[32]) {
    memset(out,0,32); unsigned e=bits>>24; uint32_t m=bits&0x007fffff;
    if(!m || (bits&0x00800000) || e>34 || (m>0xff && e>33) || (m>0xffff && e>32)) return false;
    if(e<=3){m>>=8*(3-e);for(unsigned i=0;i<3;i++)out[i]=(uint8_t)(m>>(8*i));}
    else for(unsigned i=0;i<3;i++){unsigned k=e-3+i;uint8_t v=(uint8_t)(m>>(8*i));if(k<32)out[k]=v;else if(v)return false;}
    for(unsigned i=0;i<32;i++) {if(out[i])return true;} return false;
}
inline bool meets(const uint8_t hash[32],uint32_t bits){uint8_t t[32];if(!target(bits,t))return false;for(int i=31;i>=0;i--){if(hash[i]!=t[i])return hash[i]<t[i];}return true;}
// Bitcoin mainnet consensus pow limit (00000000ffff0000...). A pool-supplied
// compact value above this limit cannot designate a Bitcoin block candidate.
inline bool btc_target_ok(uint32_t bits){uint8_t t[32],limit[32];if(!target(bits,t)||!target(0x1d00ffff,limit))return false;for(int i=31;i>=0;i--){if(t[i]!=limit[i])return t[i]<limit[i];}return true;}
inline bool meets_btc(const uint8_t hash[32],uint32_t bits){return btc_target_ok(bits)&&meets(hash,bits);}
inline uint64_t en2_capacity(int len){unsigned n=len<1?1:len>4?4:(unsigned)len;return uint64_t{1}<<(8*n);}
inline uint32_t en2_value(uint32_t counter,int len){return (uint32_t)(counter%en2_capacity(len));}
inline bool rate_ok(double ghs){return std::isfinite(ghs)&&ghs>=0&&ghs<=4000;}
inline double ghs(double diff,double secs){return secs>0&&std::isfinite(diff)&&diff>=0?diff*4294967296.0/(secs*1e9):0;}
inline double chance(double ghs,double difficulty,double seconds){if(!(ghs>=0&&difficulty>0&&seconds>=0)||!std::isfinite(ghs)||!std::isfinite(difficulty)||!std::isfinite(seconds))return 0;return -std::expm1(-ghs*1e9*seconds/(difficulty*4294967296.0));}
}
