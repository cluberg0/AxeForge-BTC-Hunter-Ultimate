#!/usr/bin/env python3
"""Verify the production backoff exit path: IO failure must not bypass delay."""
import pathlib,tempfile,subprocess
r=pathlib.Path(__file__).resolve().parents[1];s=(r/'upstream/main/stratum/pools.cpp').read_text();a=s.index('        if (healthy) backoff_s=2;');b=s.index('\n    }\n}',a);block=s[a:b]
code=r'''
#include <atomic>
#include <cassert>
#include "core/net_policy.h"
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
static int waited=-1;
int ulTaskNotifyTake(int,int ms){waited=ms;return 0;}
int retry(int backoff_s,bool healthy,bool io_restart,bool edited){
 struct Pool{bool restart;std::atomic<uint32_t>config_epoch{1};}p{io_restart};
 const uint32_t config_generation=1;if(edited)p.config_epoch=2;waited=-1;
'''+block+r'''
 return backoff_s;}
int main(){
 assert(retry(2,false,true,false)==4&&waited==2000); // failed write sets restart, still wait
 assert(retry(60,false,true,false)==60&&waited==60000);
 assert(retry(60,true,true,false)==2&&waited==2000); // long healthy session restores fast recovery
 retry(60,false,true,true);assert(waited==-1); // explicit settings change stays immediate
 assert(retry(32,false,false,false)==60&&waited==32000);
}
'''
with tempfile.TemporaryDirectory()as d:
 p=pathlib.Path(d)/'test.cpp';p.write_text(code);e=pathlib.Path(d)/'test';subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(r/'overlay/main'),str(p),'-o',str(e)],check=True);subprocess.run([str(e)],check=True)
print('PASS production reconnect: write/restart cannot bypass bounded backoff; healthy reset precedes wait; manual edits immediate')
