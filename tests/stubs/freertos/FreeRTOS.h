#pragma once
#define pdMS_TO_TICKS(x) (x)
constexpr int pdTRUE=1,pdPASS=1;
using portMUX_TYPE=int;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
