#!/usr/bin/env python3
"""Exercise production miner pause/final-send code under deterministic thread interleavings.
Extracts the real protected block and pause function; no copy of the lock logic.
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'upstream'
s = (SOURCE / 'main/mining/miner.cpp').read_text()
anchor = s.index('// pause(true) takes this same lock')
start = s.index('        xSemaphoreTake(s_work_lock, portMAX_DELAY);', anchor)
end = s.index('\n\n        hunter::job_sent(', start)
final_send = s[start:end]
start = s.index('void pause(bool p)\n{')
end = s.index('\nvoid kick()', start)
pause = s[start:end]
harness = r'''
#include <atomic>
#include <cassert>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <thread>
using SemaphoreHandle_t=std::mutex*;
constexpr unsigned portMAX_DELAY=0xffffffffu;
struct Work {bool valid=false;unsigned value=0;};
static std::mutex work_mutex, gate;
static SemaphoreHandle_t s_work_lock=&work_mutex;
static std::atomic<bool> s_paused{false}, powered{true}, pool_ready{true};
static Work s_work[32];
static uint32_t s_job_counter=0;
static void *s_job_task=reinterpret_cast<void*>(1);
static std::atomic<unsigned> sent{0}, masks{0}, notifications{0};
static std::condition_variable changed;
static bool block_send=false,send_entered=false,release_send=false,pause_attempted=false;
static thread_local bool pausing_thread=false;
static void xSemaphoreTake(SemaphoreHandle_t lock,unsigned){
 if(pausing_thread){std::lock_guard<std::mutex> lk(gate);pause_attempted=true;changed.notify_all();}
 lock->lock();
}
static void xSemaphoreGive(SemaphoreHandle_t lock){lock->unlock();}
static void xTaskNotifyGive(void*){++notifications;}
namespace board {static bool is_powered(){return powered;}}
namespace pools {static bool ready(int){return pool_ready;}}
namespace asic {
 static unsigned job_slot(uint32_t n){return n%32;}
 static void set_difficulty_mask(uint32_t){++masks;}
 static void set_version_mask(uint32_t){++masks;}
 static void send_job(uint32_t n,unsigned value){
  assert(s_work[job_slot(n)].valid&&s_work[job_slot(n)].value==value);
  std::unique_lock<std::mutex> lk(gate);
  send_entered=true;changed.notify_all();
  if(block_send)changed.wait(lk,[]{return release_send;});
  ++sent;
 }
}
static uint32_t asic_difficulty(double){return 256;}
static void publish(Work w){
 const int p=0;const double min_diff=1;const uint32_t roll_mask=0x1fffe000;
 const unsigned cj=w.value;
 for(int attempt=0;attempt<1;++attempt){
'''
checks = r'''
 }
}
'''
main = r'''
int main(){
 // A normal send sees its verification slot already published.
 publish({true,11});assert(sent==1&&s_work[0].valid&&s_work[0].value==11);
 pause(true);assert(s_paused);for(const auto &w:s_work)assert(!w.valid);
 const auto base=sent.load();const auto previous_masks=masks.load();
 for(unsigned i=0;i<100;++i)publish({true,i});
 assert(sent==base&&masks==previous_masks); // no send after pause returns
 pause(false);assert(!s_paused&&notifications==1);
 // Pause must wait for a send that already owns the production work lock.
 {std::lock_guard<std::mutex> lk(gate);block_send=true;send_entered=release_send=pause_attempted=false;}
 std::thread sender([]{publish({true,22});});
 {std::unique_lock<std::mutex> lk(gate);changed.wait(lk,[]{return send_entered;});}
 std::atomic<bool> pause_returned{false};
 std::thread pauser([&]{pausing_thread=true;pause(true);pause_returned=true;});
 {std::unique_lock<std::mutex> lk(gate);changed.wait(lk,[]{return pause_attempted;});assert(!pause_returned);release_send=true;changed.notify_all();}
 sender.join();pauser.join();assert(pause_returned&&sent==base+1);
 for(const auto &w:s_work)assert(!w.valid);
 // Work built before pause but delayed before publication must be rejected.
 pause(false);std::mutex build_mutex;std::condition_variable build_changed;
 bool built=false,release_builder=false;
 std::thread delayed([&]{
  Work built_work{true,33};
  {std::unique_lock<std::mutex> lk(build_mutex);built=true;build_changed.notify_all();build_changed.wait(lk,[&]{return release_builder;});}
  publish(built_work);
 });
 {std::unique_lock<std::mutex> lk(build_mutex);build_changed.wait(lk,[&]{return built;});}
 pause(true);const auto before_release=sent.load();
 {std::lock_guard<std::mutex> lk(build_mutex);release_builder=true;build_changed.notify_all();}
 delayed.join();assert(sent==before_release);
 // Power/pool state is rechecked inside the final production barrier.
 {std::lock_guard<std::mutex> lk(gate);block_send=false;}
 pause(false);powered=false;publish({true,44});powered=true;pool_ready=false;publish({true,55});pool_ready=true;
 assert(sent==before_release);
 publish({true,66});assert(sent==before_release+1);
 // Calling pause before start allocated the mutex remains safe.
 s_work_lock=nullptr;pause(true);assert(s_paused);pause(false);assert(!s_paused);s_work_lock=&work_mutex;
 std::puts("PASS: actual miner send/pause barrier publishes before send, waits for in-flight send, rejects delayed work after pause and rechecks powered/pool state");
}
'''
with tempfile.TemporaryDirectory() as d:
    source = pathlib.Path(d) / 'pause.cpp'
    binary = pathlib.Path(d) / 'pause'
    source.write_text(harness + final_send + checks + pause + main)
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=15)
