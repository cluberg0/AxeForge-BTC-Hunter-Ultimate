#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

namespace asic_frame {
// Poly x^5+x^2+1, initial 0x1f, MSB first. Same recurrence as the
// pinned driver's TX CRC. BM1370 RX payload plus final CRC has remainder 0.
inline uint8_t crc5(const uint8_t *data, size_t len)
{
    uint8_t c=0x1f;
    for(size_t i=0;i<len;i++)for(int b=7;b>=0;b--){
        uint8_t n=((c>>4)^(data[i]>>b))&1;
        c=((c<<1)|n)^(n<<2);c&=0x1f;
    }
    return c;
}
// Fixed storage, no heap; consumes at most one frame's remaining bytes.
// A damaged frame slides by one byte and keeps every possible following
// preamble. Partial frames survive UART timeouts, rather than flushing RX.
template<size_t N> class Collector {
    static_assert(N>=3,"frame length");
    uint8_t bytes[N]{};
    size_t used=0;
public:
    uint32_t crc_errors=0, noise_bytes=0;
    size_t needed() const { return N-used; }
    void reset() { used=0; }
    bool push(uint8_t byte,uint8_t out[N]) {
        bytes[used++]=byte;
        while(used && (bytes[0]!=0xaa || (used>=2 && bytes[1]!=0x55))){
            memmove(bytes,bytes+1,--used);noise_bytes++;
        }
        if(used<N)return false;
        if(crc5(bytes+2,N-2)==0){memcpy(out,bytes,N);used=0;return true;}
        crc_errors++;
        memmove(bytes,bytes+1,--used);
        while(used && (bytes[0]!=0xaa || (used>=2 && bytes[1]!=0x55))){
            memmove(bytes,bytes+1,--used);noise_bytes++;
        }
        return false;
    }
};
}
