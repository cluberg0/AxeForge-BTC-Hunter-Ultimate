#!/usr/bin/env python3
"""Execute the actual patched OTA HTTP handler with a deterministic socket/flash fake.
No ESP32, flash device or network connection is used.
"""
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'upstream'
s = (SOURCE / 'main/net/web.cpp').read_text()
start = s.index('static esp_err_t ota_post(httpd_req_t *req)')
end = s.index('\n// Self-update:', start)
handler = s[start:end]
harness = r'''
#include <cassert>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <vector>
#include <algorithm>
using esp_err_t=int;
constexpr int ESP_OK=0, HTTPD_400_BAD_REQUEST=400, HTTPD_500_INTERNAL_SERVER_ERROR=500, HTTPD_SOCK_ERR_TIMEOUT=-3;
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
#define AF_BOARD_ID "gamma"
struct httpd_req_t { size_t content_len; };
struct esp_partition_t { unsigned size=4*1024*1024; const char *label="ota_0"; };
static esp_partition_t partition;
static bool no_partition=false, fail_alloc=false;
static unsigned begins=0, feeds=0, aborts=0, finishes=0, armed=0, reboots=0, reads=0;
static std::vector<int> input;
static size_t cursor=0;
static void *test_malloc(size_t n) { return fail_alloc ? nullptr : std::malloc(n); }
static const esp_partition_t *esp_ota_get_next_update_partition(void*) {return no_partition?nullptr:&partition;}
namespace fwupdate { struct Writer {
 bool open=false;
 ~Writer(){ if(open)abort(); }
 bool begin(){++begins;open=true;return true;}
 bool feed(const char*,int){++feeds;return true;}
 void abort(){if(open)++aborts;open=false;}
 bool finish(){++finishes;open=false;return true;}
 const char *error(){return "fake";}
 bool wrong_board(){return false;}
 const char *found_board(){return "gamma";}
 const esp_partition_t *partition(){return &::partition;}
}; }
namespace ota_guard {static void armed(const esp_partition_t*){++::armed;}}
static esp_err_t httpd_resp_send_err(httpd_req_t*,int code,const char*){return code;}
static esp_err_t httpd_resp_sendstr(httpd_req_t*,const char*){return ESP_OK;}
static int httpd_req_recv(httpd_req_t*,char *buf,int n){
 ++reads;int out=cursor<input.size()?input[cursor++]:n;
 if(out>0){out=std::min(out,n);std::memset(buf,0,size_t(out));}
 return out;
}
static void schedule_reboot(httpd_req_t*){++reboots;}
#define malloc test_malloc
'''
checks = r'''
#undef malloc
static void reset(){begins=feeds=aborts=finishes=armed=reboots=reads=0;cursor=0;input.clear();no_partition=fail_alloc=false;}
int main(){
 httpd_req_t request{0x10000};
 reset();input={-3,-3,-3};assert(ota_post(&request)==400&&reads==3&&aborts==1&&finishes==0&&armed==0&&reboots==0);
 reset();input={-3,-3,4096,-3,-3,4096};assert(ota_post(&request)==0&&feeds==16&&finishes==1&&armed==1&&reboots==1&&aborts==0);
 reset();input={4096,0};assert(ota_post(&request)==400&&aborts==1&&finishes==0&&reboots==0);
 reset();fail_alloc=true;assert(ota_post(&request)==500&&aborts==1&&reads==0&&finishes==0);
 reset();no_partition=true;assert(ota_post(&request)==500&&begins==0&&reads==0);
 reset();request.content_len=1;assert(ota_post(&request)==400&&begins==0&&reads==0);
 reset();request.content_len=4*1024*1024+1;assert(ota_post(&request)==400&&begins==0&&reads==0);
 std::puts("PASS: actual OTA handler aborts abandoned upload, tolerates temporary stalls, cleans up dropped/OOM uploads, rejects invalid sizes; no reboot/boot selection on failure");
}
'''
with tempfile.TemporaryDirectory() as d:
    source = pathlib.Path(d) / 'ota.cpp'
    binary = pathlib.Path(d) / 'ota'
    source.write_text(harness + handler + checks)
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

# Use the real NVS read branch with allocator and NVS faults. The outer legacy
# migration branch is irrelevant here; no copied implementation is maintained.
settings_source = (SOURCE / 'main/core/settings.cpp').read_text()
start = settings_source.index('    if (nvs_get_str(h, "pools", NULL, &len)')
opening = settings_source.index('{', start)
depth, end = 1, opening + 1
while depth:
    if settings_source[end] == '{':
        depth += 1
    elif settings_source[end] == '}':
        depth -= 1
    end += 1
read_branch = settings_source[start:end]
nvs_harness = r'''
#include <cassert>
#include <cstdlib>
#include <cstdio>
#include <cstring>
using nvs_handle_t=unsigned;
constexpr int ESP_OK=0, ESP_FAIL=-1;
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
static bool fail_alloc=false,fail_query=false,fail_read=false;
static unsigned calls=0,parsed=0;
static void *test_malloc(size_t n){return fail_alloc?nullptr:std::malloc(n);}
static int nvs_get_str(nvs_handle_t,const char*,char *out,size_t *n){
 ++calls;
 if(!out){*n=3;return fail_query?ESP_FAIL:ESP_OK;}
 if(fail_read)return ESP_FAIL;
 std::memcpy(out,"[]",3);return ESP_OK;
}
static void pools_from_json(const char *json){assert(json&&std::strcmp(json,"[]")==0);++parsed;}
#define malloc test_malloc
static void load_saved_pools(){nvs_handle_t h=1;size_t len=0;
'''
nvs_checks = r'''
}
#undef malloc
int main(){
 load_saved_pools();assert(calls==2&&parsed==1);
 calls=parsed=0;fail_alloc=true;load_saved_pools();assert(calls==1&&parsed==0);
 calls=parsed=0;fail_alloc=false;fail_read=true;load_saved_pools();assert(calls==2&&parsed==0);
 calls=parsed=0;fail_read=false;fail_query=true;load_saved_pools();assert(calls==1&&parsed==0);
 std::puts("PASS: actual saved-pools NVS read branch handles allocation/query/read failure without parsing invalid memory or erasing settings");
}
'''
with tempfile.TemporaryDirectory() as d:
    source = pathlib.Path(d) / 'nvs.cpp'
    binary = pathlib.Path(d) / 'nvs'
    source.write_text(nvs_harness + read_branch + nvs_checks)
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
