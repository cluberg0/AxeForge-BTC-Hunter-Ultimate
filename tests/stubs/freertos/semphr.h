#pragma once
using SemaphoreHandle_t=void*;
SemaphoreHandle_t xSemaphoreCreateMutex();int xSemaphoreTake(SemaphoreHandle_t,unsigned);int xSemaphoreGive(SemaphoreHandle_t);
