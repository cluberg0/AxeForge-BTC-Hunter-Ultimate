#include <cassert>
#include <algorithm>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
namespace hunter { bool candidate_snapshot(char hash[65], int &pool); }
#include "../overlay/main/core/guardian.cpp"

MinerState g_state{};
static int64_t now_us=1000000;
static bool wifi_on=true,candidate_available=false,nvs_fail=false,task_success=true;
static std::string candidate_hash(64,'0'),http_body,request_body,response;
static std::vector<unsigned char> persisted;
static unsigned http_calls=0,notices=0,cleanups=0;
static int http_status=200;
static bool init_ok=true,open_ok=true,complete_data=true,read_error=false;
static size_t read_pos=0,read_chunk=1024;
static int64_t read_delay=0;
static bool disable_during_read=false,replace_during_read=false;
static bool config_held=false;
int64_t esp_timer_get_time(){return now_us;}
namespace wifi {bool connected(){return wifi_on;}}
namespace hunter {bool candidate_snapshot(char hash[65],int &pool){if(!candidate_available)return false;memcpy(hash,candidate_hash.c_str(),65);pool=0;return true;}}
namespace notify {void post(int,const char*,...){notices++;}}
int esp_crt_bundle_attach(void*){return ESP_OK;}
esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t*c){assert(c->crt_bundle_attach==esp_crt_bundle_attach&&c->disable_auto_redirect&&c->timeout_ms==4000);assert(std::string(c->url)=="https://mempool.space/api/block/"+candidate_hash+"/status");http_calls++;read_pos=0;return init_ok?reinterpret_cast<void*>(1):nullptr;}
int esp_http_client_open(esp_http_client_handle_t,int){return open_ok?ESP_OK:ESP_FAIL;}
int esp_http_client_fetch_headers(esp_http_client_handle_t){return int(http_body.size());}
int esp_http_client_get_status_code(esp_http_client_handle_t){return http_status;}
int httpd_req_recv(httpd_req_t*,char*p,size_t n){memcpy(p,request_body.data(),n);return int(n);}
int httpd_resp_send_err(httpd_req_t*,int n,const char*s){response=s;return n;}
int httpd_resp_sendstr(httpd_req_t*,const char*s){response=s;return ESP_OK;}
int httpd_resp_set_type(httpd_req_t*,const char*){return ESP_OK;}
int httpd_resp_set_hdr(httpd_req_t*,const char*key,const char*value){assert(!strcmp(key,"Cache-Control")&&!strcmp(value,"no-store"));return ESP_OK;}
static int toggle(bool value){request_body=value?"{\"enabled\":true}":"{\"enabled\":false}";httpd_req_t req{int(request_body.size())};return guardian::set(&req);}
int esp_http_client_read(esp_http_client_handle_t,char*p,int max){now_us+=read_delay;if(disable_during_read){disable_during_read=false;assert(toggle(false)==ESP_OK);}if(replace_during_read){replace_during_read=false;candidate_hash[63]=candidate_hash[63]=='0'?'1':'0';}if(read_error)return -1;size_t n=std::min({size_t(max),read_chunk,http_body.size()-read_pos});memcpy(p,http_body.data()+read_pos,n);read_pos+=n;return int(n);}
bool esp_http_client_is_complete_data_received(esp_http_client_handle_t){return complete_data&&read_pos==http_body.size();}
int esp_http_client_cleanup(esp_http_client_handle_t){cleanups++;return ESP_OK;}
SemaphoreHandle_t xSemaphoreCreateMutex(){return reinterpret_cast<void*>(1);}
int xSemaphoreTake(SemaphoreHandle_t,unsigned){if(config_held)return 0;config_held=true;return pdTRUE;}
int xSemaphoreGive(SemaphoreHandle_t){assert(config_held);config_held=false;return pdTRUE;}
void vTaskDelay(unsigned){}
int xTaskCreatePinnedToCoreWithCaps(void(*)(void*),const char*,unsigned stack,void*,unsigned,void*,int,unsigned cap){assert(stack==8192&&cap==MALLOC_CAP_SPIRAM);return task_success?pdPASS:0;}
int nvs_open(const char*ns,int,nvs_handle_t*h){assert(!strcmp(ns,"af_guardian"));*h=1;return ESP_OK;}
int nvs_get_blob(nvs_handle_t,const char*,void*p,size_t*n){if(persisted.size()!=*n)return ESP_FAIL;memcpy(p,persisted.data(),*n);return ESP_OK;}
int nvs_set_blob(nvs_handle_t,const char*,const void*p,size_t n){if(nvs_fail)return ESP_FAIL;auto b=static_cast<const unsigned char*>(p);persisted={b,b+n};return ESP_OK;}
int nvs_commit(nvs_handle_t){return nvs_fail?ESP_FAIL:ESP_OK;}
void nvs_close(nvs_handle_t){}
static void next_tick(){now_us+=61000000;guardian::tick();}
int main(){
 guardian::start();assert(guardian::task_ok&&!guardian::status.enabled&&guardian::status.state==5);
 guardian::tick();assert(http_calls==0);
 nvs_fail=true;assert(toggle(true)==500&&!guardian::status.enabled);nvs_fail=false;
 assert(toggle(true)==0&&guardian::status.enabled);guardian::tick();assert(http_calls==0);
 candidate_available=true;g_state.time_synced=false;guardian::tick();assert(guardian::status.state==4&&std::string(guardian::status.error)=="time_unsynced"&&http_calls==0);
 g_state.time_synced=true;wifi_on=false;next_tick();assert(std::string(guardian::status.error)=="offline"&&http_calls==0);wifi_on=true;
 http_status=404;next_tick();assert(guardian::status.state==2&&!guardian::status.in_best_chain&&http_calls==1);
 next_tick();assert(http_calls==2);guardian::tick();assert(http_calls==2); // throttled
 http_status=302;next_tick();assert(guardian::status.state==4&&notices==0);
 http_status=200;http_body="{\"in_best_chain\":true,\"height\":0}";next_tick();assert(guardian::status.state==3&&guardian::status.in_best_chain&&guardian::status.height==0&&notices==1);
 next_tick();assert(notices==1); // no repeated confirmation notice
 http_body="{\"in_best_chain\":false}";next_tick();assert(guardian::status.state==3&&!guardian::status.in_best_chain);
 http_body="{\"in_best_chain\":true,\"height\":42.5}";next_tick();assert(guardian::status.state==4&&std::string(guardian::status.error)=="invalid_response");
 http_body=std::string(17,'[')+std::string(17,']');next_tick();assert(guardian::status.state==4);
 http_body="{\"in_best_chain\":true,\"height\":850000}";complete_data=false;next_tick();assert(std::string(guardian::status.error)=="incomplete_response");complete_data=true;
 read_error=true;next_tick();assert(std::string(guardian::status.error)=="incomplete_response");read_error=false;
 http_body=std::string(1000,' ');next_tick();assert(std::string(guardian::status.error)=="incomplete_response");
 init_ok=false;next_tick();assert(std::string(guardian::status.error)=="no_memory");init_ok=true;
 read_chunk=1;read_delay=6000000;http_body="{\"in_best_chain\":true,\"height\":850000}";next_tick();assert(std::string(guardian::status.error)=="incomplete_response");read_delay=0;read_chunk=1024;
 replace_during_read=true;next_tick();assert(guardian::status.state==4); // result for preceding candidate discarded
 next_tick();assert(guardian::status.state==3&&guardian::status.in_best_chain&&guardian::status.height==850000);
 disable_during_read=true;next_tick();assert(!guardian::status.enabled&&guardian::status.state==5);
 unsigned calls=http_calls;next_tick();assert(http_calls==calls);
 assert(toggle(true)==0);next_tick();assert(guardian::status.state==3);
 now_us+=guardian::DAY_US;guardian::tick();assert(guardian::status.state==4&&std::string(guardian::status.error)=="expired");calls=http_calls;guardian::tick();assert(http_calls==calls);
 request_body="{\"enabled\":0}";httpd_req_t invalid{int(request_body.size())};assert(guardian::set(&invalid)==400);
 guardian::task_ok=false;assert(toggle(false)==500);guardian::task_ok=true;
 request_body=std::string(17,'[')+std::string(17,']');httpd_req_t deep{int(request_body.size())};assert(guardian::set(&deep)==400);
 persisted={1,2};guardian::status=guardian::Observation{};guardian::start();assert(!guardian::status.enabled);
 persisted={1,1};task_success=false;guardian::start();assert(!guardian::task_ok&&guardian::status.enabled&&std::string(guardian::status.error)=="task_unavailable");
 httpd_req_t req{};assert(guardian::get(&req)==0);cJSON*j=cJSON_Parse(response.c_str());assert(j);cJSON_Delete(j);
 if(getenv("AXEFORGE_API_JSON"))std::cout<<"API_JSON "<<response<<'\n';
 assert(cleanups+1==http_calls); // only init OOM has no client to clean
 std::cout<<"PASS: guardian defaultoff, config/NVS failures, HTTPS/redirect/404, exact schema, malformed/truncated/deep/oversized responses, deadline, throttling, stale candidate/config race, disable and expiry\n";
}
