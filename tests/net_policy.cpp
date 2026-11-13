#include "core/net_policy.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
int main(){
 using namespace net_policy;
 assert(!idle_expired(180000000,0,true));assert(idle_expired(180000001,0,true));
 assert(!idle_expired(899000000,0,false));assert(idle_expired(900000001,0,false));assert(!idle_expired(10,20,true));
 unsigned n=2;for(unsigned e:{4u,8u,16u,32u,60u,60u}){n=next_backoff(n,false);assert(n==e);}assert(next_backoff(60,true)==2);
 Failover f;bool ok[4]={true,true,false,false};uint32_t ids[4]={1,1,1,1};assert(f.choose(ok,ids,1000000)==0);
 ok[0]=false;assert(f.choose(ok,ids,2000000)==1);ok[0]=true;assert(f.choose(ok,ids,3000000)==1);assert(f.choose(ok,ids,32999999)==1);assert(f.choose(ok,ids,33000000)==0);
 ok[0]=false;assert(f.choose(ok,ids,34000000)==1);ok[0]=true;f.choose(ok,ids,35000000);ids[0]++;assert(f.choose(ok,ids,64000000)==1);assert(f.choose(ok,ids,93000000)==1);assert(f.choose(ok,ids,94000000)==0);
 ok[0]=ok[1]=false;assert(f.choose(ok,ids,95000000)==-1);
 std::puts("PASS network policy: active/standby real-hang bounds, capped backoff, immediate failover, 30s failback/session anti-flap");
}
