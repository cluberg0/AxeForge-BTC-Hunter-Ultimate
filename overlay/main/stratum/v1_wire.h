#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>
#include "cJSON.h"

namespace v1_wire {
inline bool request_id(const cJSON *node, uint32_t &id)
{
    if (!cJSON_IsNumber(node)) return false;
    double n = node->valuedouble;
    if (!isfinite(n) || n < 0 || n > UINT32_MAX || floor(n) != n) return false;
    id = (uint32_t)n;
    return true;
}
inline bool hex_field(const char *s, size_t min_len, size_t max_len)
{
    size_t n = strlen(s);
    if (n < min_len || n > max_len || (n & 1)) return false;
    for (size_t i=0; i<n; ++i) if (!isxdigit((unsigned char)s[i])) return false;
    return true;
}
// Returns a malloc-owned, JSON-escaped, newline-terminated request and its wire
// length (excluding the trailing NUL). Exact wallet/worker bytes are retained.
inline char *request(uint32_t id, const char *method, const char *const *fields, int count, size_t &length)
{
    length = 0;
    cJSON *msg = cJSON_CreateObject();
    cJSON *params = cJSON_CreateStringArray(fields, count);
    bool built = msg && params && cJSON_AddNumberToObject(msg, "id", id) &&
                 cJSON_AddStringToObject(msg, "method", method);
    if (built) { cJSON_AddItemToObject(msg, "params", params); params = nullptr; }
    char *json = built ? cJSON_PrintUnformatted(msg) : nullptr;
    cJSON_Delete(params); cJSON_Delete(msg);
    if (!json) return nullptr;
    size_t n = strlen(json);
    char *wire = (char *)malloc(n+2);
    if (wire) { memcpy(wire,json,n); wire[n]='\n'; wire[n+1]=0; length=n+1; }
    free(json);
    return wire;
}
}
