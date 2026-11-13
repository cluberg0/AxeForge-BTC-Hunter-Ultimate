#include "mempool.h"
#include "core/state.h"
#include <cstdio>
namespace mempool {
void start(){g_state.mempool.valid=false;snprintf(g_state.mempool.error,sizeof(g_state.mempool.error),"Automatic Mempool feed removed in Ultimate 2.0");}
void refresh_now(){} // retained API compatibility; no client, timers or TLS task
}
