#pragma once
constexpr int tskNO_AFFINITY=-1;
int xTaskCreatePinnedToCoreWithCaps(void(*)(void*), const char*, unsigned, void*, unsigned, void*, int, unsigned);
