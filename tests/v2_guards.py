#!/usr/bin/env python3
"""Compile real tuner ceiling and early API validation, without duplicating policy."""
import pathlib,subprocess,tempfile
r=pathlib.Path(__file__).resolve().parents[1];s=(r/'upstream/main/core/tuner.cpp').read_text();a=s.index('static float power_ceiling()');b=s.index('// From the chips',a);ceiling=s[a:b]
s=(r/'upstream/main/net/web.cpp').read_text();a=s.index('#if defined(AF_ASIC_BM1370)',s.index('static esp_err_t settings_post'));b=s.index('    Settings &c =',a);guard=s[a:b]
code=r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cjson/cJSON.h>
#define AF_ASIC_BM1370 1
#define AF_NUM_ASICS 1
#define HTTPD_400_BAD_REQUEST 400
constexpr int GOAL_POWER_CAP=1;
struct Settings{int tune_goal=1;float power_cap_w=30;bool overclock=false;};static Settings cfg;
namespace settings{Settings&get(){return cfg;}}
namespace gates{float max_power(){return 40;}bool available(){return true;}}
namespace asic{bool pll_supported(float f,float&a){a=f;return true;}}
bool get_bool(cJSON*j,const char*k,bool d){auto*v=cJSON_GetObjectItem(j,k);return cJSON_IsBool(v)?cJSON_IsTrue(v):d;}
bool copy_str(cJSON*j,const char*k,char*b,size_t n){auto*v=cJSON_GetObjectItem(j,k);if(!cJSON_IsString(v))return false;snprintf(b,n,"%s",v->valuestring);return true;}
namespace turbo{bool active(){return false;}bool unlocked(){return false;}float power_budget(){return 25;}bool manual_check(float=-1){return true;}}
int httpd_resp_send_err(void*,int v,const char*){return v;}
'''+ceiling+r'''
static int writes=0;
int validate(cJSON*j){void*req=nullptr;
'''+guard+r'''
 cJSON_Delete(j);writes++;return 0;}
int main(){assert(power_ceiling()==25&&cfg.power_cap_w==30);cfg.power_cap_w=18;assert(power_ceiling()==18);cfg.tune_goal=0;assert(power_ceiling()==25);cfg.tune_goal=2;assert(power_ceiling()==25);cfg.tune_goal=1;cfg.power_cap_w=0;assert(power_ceiling()==25);
 assert(validate(cJSON_Parse("{\"pcap\":30}"))==400&&writes==0);assert(validate(cJSON_Parse("{\"pcap\":-1}"))==400&&writes==0);assert(validate(cJSON_Parse("{\"pcap\":25}"))==0&&writes==1);assert(validate(cJSON_Parse("{\"ssid\":\"unchanged\"}"))==0&&writes==2);assert(validate(cJSON_Parse("{\"freq\":900}"))==400);cfg.overclock=true;assert(validate(cJSON_Parse("{\"freq\":900,\"pcap\":30,\"mv\":1300}"))==0);assert(validate(cJSON_Parse("{\"freq\":1001}"))==400);assert(validate(cJSON_Parse("{\"pcap\":31}"))==400);assert(validate(cJSON_Parse("{\"mv\":1301}"))==400);
}
'''
with tempfile.TemporaryDirectory()as d:
 p=pathlib.Path(d)/'test.cpp';p.write_text(code);exe=pathlib.Path(d)/'test';subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(p),'-lcjson','-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('PASS production tuner ceiling<=25W, stored cap unchanged, unlocked accepts900MHz/30W; rejects1001MHz/1301mV/31W before mutations')
