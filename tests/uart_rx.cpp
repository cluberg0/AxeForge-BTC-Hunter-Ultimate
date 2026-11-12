#include <array>
#include <vector>
#include <cassert>
#include <cstdio>
#include "asic/rx_frame.h"
// Independent recurrence from bitaxeorg/ESP-Miner components/asic/crc.c.
static uint8_t reference_crc(const uint8_t *p,size_t n){uint8_t c=31;for(size_t i=0;i<n;i++){uint8_t b=p[i];for(int j=0;j<8;j++){uint8_t bit=b>>7;b<<=1;uint8_t x=((c>>4)^bit)&1;c=((c<<1)|x)^(x<<2);c&=31;}}return c;}
template<size_t N>static std::array<uint8_t,N> frame(uint8_t seed,bool job){std::array<uint8_t,N> f{};f[0]=0xaa;f[1]=0x55;for(size_t i=2;i<N-1;i++)f[i]=seed+i;for(unsigned c=0;c<32;c++){f[N-1]=(job?0x80:0)|c;if(reference_crc(f.data()+2,N-2)==0)return f;}assert(false);return f;}
template<size_t N>static void check(){
    auto a=frame<N>(7,true),b=frame<N>(80,false);asic_frame::Collector<N> rx;uint8_t out[N];
    for(size_t split=0;split<N;split++){
        rx.reset();for(size_t i=0;i<split;i++)assert(!rx.push(a[i],out));
        // UART timeout: no push/reset. The next read must complete this frame.
        for(size_t i=split;i<N;i++)assert(rx.push(a[i],out)==(i==N-1));
        assert(memcmp(out,a.data(),N)==0);
    }
    auto broken=a;broken[3]^=1;
    std::vector<uint8_t> stream={0x00,0x12,0xaa,0xaa,0x11};
    stream.insert(stream.end(),broken.begin(),broken.end());stream.insert(stream.end(),a.begin(),a.end());stream.insert(stream.end(),b.begin(),b.end());
    unsigned found=0;rx.reset();
    for(auto byte:stream)if(rx.push(byte,out)){assert(memcmp(out,(found?b:a).data(),N)==0);found++;}
    assert(found==2&&rx.crc_errors>0&&rx.noise_bytes>0);
    // Every possible single-bit corruption in payload/CRC is rejected, and
    // the subsequent intact candidate is recovered without flushing it.
    for(size_t i=2;i<N;i++)for(unsigned bit=0;bit<8;bit++){
        rx.reset();auto bad=a;bad[i]^=1u<<bit;found=0;
        for(auto byte:bad)assert(!rx.push(byte,out));
        for(auto byte:a)if(rx.push(byte,out)){assert(memcmp(out,a.data(),N)==0);found++;}
        assert(found==1);
    }
    // Overlapping AA-AA-55 prefix retains the second AA.
    rx.reset();assert(!rx.push(0xaa,out));found=0;for(auto byte:a)if(rx.push(byte,out))found++;assert(found==1);
    for(unsigned s=0;s<256;s++){auto f=frame<N>((uint8_t)s,s&1);assert(asic_frame::crc5(f.data()+2,N-2)==reference_crc(f.data()+2,N-2));}
}
int main(){check<11>();check<9>();puts("UART RX: BM1370 11-byte and BM1397 9-byte partial/resync/noise/CRC/back-to-back PASS");}
