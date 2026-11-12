#include <cassert>
#include <cstdio>
#include <initializer_list>
#include "stratum/v1_wire.h"
int main()
{
    uint32_t id=777;
    const char *accepted[]={"100","2147483648","4294967295"};
    const uint32_t expected[]={100,2147483648u,UINT32_MAX};
    for(unsigned i=0;i<3;i++){cJSON *j=cJSON_Parse(accepted[i]);assert(v1_wire::request_id(j,id)&&id==expected[i]);cJSON_Delete(j);}
    for(const char *bad:{"-1","100.5","4294967296","1e999","\"100\"","null"}){
        cJSON *j=cJSON_Parse(bad);id=777;assert(!v1_wire::request_id(j,id)&&id==777);cJSON_Delete(j);
    }
    assert(v1_wire::hex_field("",0,8192));
    assert(v1_wire::hex_field("00ffAB12",8,8));
    assert(!v1_wire::hex_field("0",0,8));
    assert(!v1_wire::hex_field("00xx",0,8));
    assert(!v1_wire::hex_field("00ffAB12",4,4));
    const char *fields[]={"wallet.worker\"\\\n", "job\"],\"id\":0}\n", "00000001", "12345678", "deadbeef", "00000000"};
    size_t len=0;char *wire=v1_wire::request(2147483648u,"mining.submit",fields,6,len);
    assert(wire&&len==strlen(wire)&&wire[len-1]=='\n');
    assert(strchr(wire,'\n')==wire+len-1); // credentials/job IDs cannot inject another wire command
    cJSON *root=cJSON_Parse(wire);assert(root);assert(v1_wire::request_id(cJSON_GetObjectItem(root,"id"),id)&&id==2147483648u);
    cJSON *params=cJSON_GetObjectItem(root,"params");assert(cJSON_GetArraySize(params)==6);
    for(int i=0;i<6;i++)assert(strcmp(cJSON_GetArrayItem(params,i)->valuestring,fields[i])==0);
    assert(strcmp(cJSON_GetObjectItem(root,"method")->valuestring,"mining.submit")==0);
    cJSON_Delete(root);free(wire);
    len=0;wire=v1_wire::request(3,"mining.authorize",fields,2,len);assert(wire&&len==strlen(wire));
    root=cJSON_Parse(wire);assert(root);params=cJSON_GetObjectItem(root,"params");assert(cJSON_GetArraySize(params)==2);
    assert(strcmp(cJSON_GetArrayItem(params,0)->valuestring,fields[0])==0);assert(strcmp(cJSON_GetArrayItem(params,1)->valuestring,fields[1])==0);
    cJSON_Delete(root);free(wire);
    puts("V1 wire: uint32 IDs, fractional/nonfinite rejection, hex validation, exact escaped authorization/submit PASS");
}
