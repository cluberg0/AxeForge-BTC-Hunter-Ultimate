#pragma once
struct cJSON{double valuedouble;int valueint;};
cJSON*cJSON_Parse(const char*);cJSON*cJSON_GetObjectItem(cJSON*,const char*);cJSON*cJSON_GetArrayItem(cJSON*,int);bool cJSON_IsBool(cJSON*);bool cJSON_IsArray(cJSON*);bool cJSON_IsTrue(cJSON*);bool cJSON_IsNumber(cJSON*);int cJSON_GetArraySize(cJSON*);void cJSON_Delete(cJSON*);
