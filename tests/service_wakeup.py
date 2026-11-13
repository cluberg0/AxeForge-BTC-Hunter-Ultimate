#!/usr/bin/env python3
"""Exercise actual service worker loops with deterministic task notification fakes."""
import pathlib,tempfile,subprocess
r=pathlib.Path(__file__).resolve().parents[1]
s=(r/'upstream/main/net/swarm.cpp').read_text();a=s.index('static void swarm_task(');b=s.index('// ------------------------------------------------------------------ API',a);swarm=s[a:b]
s=(r/'upstream/main/net/fwupdate.cpp').read_text();a=s.index('static void task(void *)');b=s.index('\nvoid start()',a);updater=s[a:b]
a=s.index('static bool auto_ok()');b=s.index('// Flash writes',a);auto_guard=s[a:b]
s=(r/'upstream/main/net/price.cpp').read_text();a=s.index('void start()',s.index('namespace price {'));b=s.index('void refresh_now()',a);price_start=s[a:b]
code=r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include <cmath>
struct Stop{};
#define pdTRUE 1
#define portMAX_DELAY 0xffffffffu
#define pdMS_TO_TICKS(x) (x)
#define ESP_LOGW(...) ((void)0)
namespace wifi{bool connected(){return true;}}
struct{char ip[16]="192.168.1.2";}g_state;
static bool s_scan=false,s_scanning=false;static int events=0,polls=0,scans=0;
unsigned ulTaskNotifyTake(int,unsigned timeout){assert(timeout==portMAX_DELAY);if(!events--)throw Stop{};return 1;}
void scan(){scans++;}void poll_all(){polls++;}
'''+swarm+r'''
namespace update {
static bool s_check_req=false,s_install_req=false;static char s_failed_tag[24]{};
static struct{bool newer=false;char latest[24]="release";}s_info;
static int steps=0,limit=3,checks=0,installs=0;
void vTaskDelay(unsigned){if(++steps>limit)throw Stop{};}
void do_check(){checks++;s_info.newer=true;}void spawn_install(){installs++;}
'''+auto_guard+r'''
'''+updater+r'''
}
namespace price {static float s_now=42;static bool s_have=true,s_pause=true;static char s_err[64];
'''+price_start+r'''
}
int main(){
 price::start();assert(std::isnan(price::s_now)&&!price::s_have&&!price::s_pause);
 try{swarm_task(nullptr);}catch(Stop&){}assert(polls==0&&scans==0);
 events=1;try{swarm_task(nullptr);}catch(Stop&){}assert(polls==1&&scans==0);
 events=1;s_scan=true;try{swarm_task(nullptr);}catch(Stop&){}assert(polls==2&&scans==1&&!s_scan&&!s_scanning);
 try{update::task(nullptr);}catch(Stop&){}assert(update::checks==0&&update::installs==0);
 update::steps=0;update::s_check_req=true;try{update::task(nullptr);}catch(Stop&){}assert(update::checks==1&&update::installs==0);
 update::steps=0;update::s_install_req=true;try{update::task(nullptr);}catch(Stop&){}assert(update::installs==1);
}
'''
with tempfile.TemporaryDirectory()as d:
 p=pathlib.Path(d)/'test.cpp';p.write_text(code);e=pathlib.Path(d)/'test';subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(p),'-o',str(e)],check=True);subprocess.run([str(e)],check=True)
print('PASS production services: farm waits for explicit notification; update HTTP/manual install only on request, never timer/autonomous install')
