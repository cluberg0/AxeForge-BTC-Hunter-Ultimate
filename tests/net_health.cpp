#include <cassert>
#include <cstring>
#include <string>
#include <iostream>
#include "../overlay/main/core/net_health.cpp"
static int64_t now_us=1000000;
static std::string body,response;static int offset=0;static bool fail_clock=false;static size_t input_pos=0;
int64_t esp_timer_get_time(){return now_us;}
namespace weather{int offset_minutes(){return offset;}bool set_offset_minutes(int value){if(fail_clock)return false;offset=value;return true;}}
int httpd_req_recv(httpd_req_t*,char*p,size_t n){n=std::min(n,body.size()-input_pos);memcpy(p,body.data()+input_pos,n);input_pos+=n;return int(n);}
int httpd_resp_send_err(httpd_req_t*,int status,const char*s){response=s;return status;}
int httpd_resp_sendstr(httpd_req_t*,const char*s){response=s;return 0;}
int httpd_resp_set_type(httpd_req_t*,const char*){return 0;}
int httpd_resp_set_hdr(httpd_req_t*,const char*,const char*){return 0;}
static int command(std::string s){body=s;input_pos=0;httpd_req_t r{int(s.size())};return net_health::set(&r);}
static cJSON*get(){httpd_req_t r{};assert(net_health::get(&r)==0);auto*j=cJSON_Parse(response.c_str());assert(j);return j;}
static double num(cJSON*j,const char*k){auto*v=cJSON_GetObjectItem(j,k);assert(cJSON_IsNumber(v));return v->valuedouble;}
int main(){
 using namespace net_health;
 attempt(0);connected(0);received(0,100);processed(0,100);processed(0,5000);selected(0);assert(active(0)&&!active(1));now_us+=6000000;assert(!active(0));now_us=21000000;disconnected(0);now_us=31000000;
 for(auto e:{Error::Connect,Error::Read,Error::Write,Error::Idle,Error::Malformed})error(0,e);
 auto*j=get();auto*row=cJSON_GetArrayItem(cJSON_GetObjectItem(j,"pools"),0);assert(num(row,"upSeconds")==20&&num(row,"downSeconds")==10&&num(row,"meanProcessingMs")==2.55&&num(row,"maxProcessingMs")==5);assert(num(row,"idleReconnects")==1);cJSON_Delete(j);
 attempt(0);connected(0);now_us+=9000000;j=get();row=cJSON_GetArrayItem(cJSON_GetObjectItem(j,"pools"),0);assert(num(row,"reconnects")==1&&num(row,"upSeconds")==29);cJSON_Delete(j);
 received(-1,2);error(4,Error::Read);processed(0,-1);assert(command("{\"utcOffsetMinutes\":600}")==0&&offset==600);assert(command("{\"utcOffsetMinutes\":840}")==0);assert(command("{\"utcOffsetMinutes\":841}")==400);assert(command("{\"utcOffsetMinutes\":1.1}")==400);assert(command("{\"utcOffsetMinutes\":true}")==400);assert(command("{")==400);fail_clock=true;assert(command("{\"utcOffsetMinutes\":-720}")==500&&offset==840);
 rows[0].rx_bytes=uint64_t(UINT32_MAX)+100;j=get();cJSON_Delete(j);std::string saved=response;
 if(getenv("AXEFORGE_API_JSON"))std::cout<<"API_JSON "<<saved<<'\n';
 std::cout<<"PASS exact event-driven network diagnostics, errors/reconnects/latency, 64-bit counters, activity freshness, UTC validation/write failure\n";
}
