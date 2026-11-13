#include "net_health.h"
#include "core/state.h"
#include "core/json_util.h"
#include "net/weather.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cmath>
namespace net_health {
namespace {
constexpr int N=4;
struct Stats {
 uint64_t attempts=0,reconnects=0,rx_bytes=0,messages=0,processing_us=0,max_processing_us=0,errors[5]={};
 int64_t started=0,up_since=0,up_us=0,last_rx=0;
 bool online=false;
};
Stats rows[N];portMUX_TYPE mux=portMUX_INITIALIZER_UNLOCKED;
std::atomic<int> chosen{-1};
std::atomic<uint32_t> selection_ms{0};
bool valid(int p){return p>=0&&p<N;}
bool append(char*b,size_t cap,size_t&n,const char*fmt,...) __attribute__((format(printf,4,5)));
bool append(char*b,size_t cap,size_t&n,const char*fmt,...){va_list a;va_start(a,fmt);int k=vsnprintf(b+n,cap-n,fmt,a);va_end(a);if(k<0||size_t(k)>=cap-n)return false;n+=size_t(k);return true;}
}
void attempt(int p){if(!valid(p))return;int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);auto&s=rows[p];if(s.attempts++)s.reconnects++;else s.started=now;portEXIT_CRITICAL(&mux);}
void connected(int p){if(!valid(p))return;int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);auto&s=rows[p];if(!s.online){s.online=true;s.up_since=now;}portEXIT_CRITICAL(&mux);}
void disconnected(int p){if(!valid(p))return;int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);auto&s=rows[p];if(s.online){s.up_us+=now-s.up_since;s.online=false;}portEXIT_CRITICAL(&mux);}
void received(int p,uint32_t n){if(!valid(p))return;int64_t now=esp_timer_get_time();portENTER_CRITICAL(&mux);rows[p].last_rx=now;rows[p].rx_bytes+=n;portEXIT_CRITICAL(&mux);}
void processed(int p,int64_t us){if(!valid(p)||us<0)return;portENTER_CRITICAL(&mux);auto&s=rows[p];s.messages++;s.processing_us+=uint64_t(us);if(uint64_t(us)>s.max_processing_us)s.max_processing_us=uint64_t(us);portEXIT_CRITICAL(&mux);}
void error(int p,Error e){if(!valid(p))return;unsigned i=unsigned(e);if(i>=5)return;portENTER_CRITICAL(&mux);rows[p].errors[i]++;portEXIT_CRITICAL(&mux);}
void selected(int p){selection_ms.store(uint32_t(esp_timer_get_time()/1000));chosen.store(valid(p)?p:-1);}
bool active(int p){return chosen.load()==p&&uint32_t(esp_timer_get_time()/1000)-selection_ms.load()<=5000;}
esp_err_t get(httpd_req_t*req){
 Stats snap[N];portENTER_CRITICAL(&mux);for(int i=0;i<N;i++)snap[i]=rows[i];portEXIT_CRITICAL(&mux);
 int64_t now=esp_timer_get_time();constexpr size_t cap=4096;char*b=static_cast<char*>(malloc(cap));if(!b)return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"no memory");size_t n=0;
 bool ok=append(b,cap,n,"{\"version\":2,\"weatherPolling\":false,\"mempoolPolling\":false,\"utcOffsetMinutes\":%d,\"activePool\":%d,\"freeInternal\":%lu,\"minimumInternal\":%lu,\"pools\":[",weather::offset_minutes(),chosen.load(),(unsigned long)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),(unsigned long)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL));
 for(int i=0;i<N&&ok;i++){const auto&s=snap[i];int64_t span=s.attempts?now-s.started:0;int64_t up=s.up_us+(s.online?now-s.up_since:0);if(span<0)span=0;if(up<0)up=0;if(up>span)up=span;
 ok=append(b,cap,n,"%s{\"slot\":%d,\"tcpConnected\":%s,\"attempts\":%llu,\"reconnects\":%llu,\"upSeconds\":%.3f,\"downSeconds\":%.3f,\"rxBytes\":%llu,\"lastRxAgeSeconds\":%.3f,\"messages\":%llu,\"meanProcessingMs\":%.3f,\"maxProcessingMs\":%.3f,\"connectErrors\":%llu,\"readErrors\":%llu,\"writeErrors\":%llu,\"idleReconnects\":%llu,\"malformedMessages\":%llu}",i?",":"",i,s.online?"true":"false",(unsigned long long)s.attempts,(unsigned long long)s.reconnects,up/1e6,(span-up)/1e6,(unsigned long long)s.rx_bytes,s.last_rx?(now-s.last_rx)/1e6:-1.,(unsigned long long)s.messages,s.messages?double(s.processing_us)/s.messages/1000.:0.,s.max_processing_us/1000.,(unsigned long long)s.errors[0],(unsigned long long)s.errors[1],(unsigned long long)s.errors[2],(unsigned long long)s.errors[3],(unsigned long long)s.errors[4]);}
 ok=ok&&append(b,cap,n,"]}");esp_err_t result;if(!ok)result=httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"response overflow");else {httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");result=httpd_resp_sendstr(req,b);}free(b);return result;
}
esp_err_t set(httpd_req_t*req){char body[96];if(req->content_len<=0||size_t(req->content_len)>=sizeof(body))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"bad body");int used=0;while(used<req->content_len){int n=httpd_req_recv(req,body+used,req->content_len-used);if(n<=0)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"incomplete body");used+=n;}body[used]=0;cJSON*j=json_parse(body);cJSON*v=j?cJSON_GetObjectItem(j,"utcOffsetMinutes"):nullptr;bool good=cJSON_IsNumber(v)&&std::isfinite(v->valuedouble)&&std::floor(v->valuedouble)==v->valuedouble&&v->valuedouble>=-720&&v->valuedouble<=840;int minutes=good?int(v->valuedouble):0;cJSON_Delete(j);if(!good)return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"UTC offset must be integer minutes -720..840");if(!weather::set_offset_minutes(minutes))return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"clock write failed");return httpd_resp_sendstr(req,"OK");}
}
