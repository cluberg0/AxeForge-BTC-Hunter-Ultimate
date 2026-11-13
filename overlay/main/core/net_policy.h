#pragma once
#include <cstdint>
#include <algorithm>
namespace net_policy {
// A connected standby can legitimately receive no share replies. Still bound
// application silence, and use kernel TCP keepalive to detect dead peers sooner.
constexpr int64_t active_idle_us=180000000LL, standby_idle_us=900000000LL;
inline bool idle_expired(int64_t now,int64_t last,bool active){return now>=last&&now-last>(active?active_idle_us:standby_idle_us);}
inline unsigned next_backoff(unsigned old,bool healthy){return healthy?2:std::min(60u,old>30?60u:old*2);}
struct Failover {
 int current=-1;
 int64_t since[4]={};
 uint32_t session[4]={};
 int choose(const bool ok[4],const uint32_t ids[4],int64_t now){
  for(int i=0;i<4;i++){if(!ok[i])since[i]=0;else if(!since[i]||session[i]!=ids[i])since[i]=now?now:1;session[i]=ids[i];}
  int first=-1;for(int i=0;i<4;i++)if(ok[i]){first=i;break;}
  if(current<0||!ok[current])return current=first; // fail over immediately
  if(first>=0&&first<current&&now-since[first]>=30000000LL)current=first;
  return current;
 }
};
}
