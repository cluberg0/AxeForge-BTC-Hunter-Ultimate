#pragma once
#include <cstddef>
using esp_err_t=int;
constexpr int ESP_OK=0,ESP_FAIL=-1,HTTPD_400_BAD_REQUEST=400,HTTPD_500_INTERNAL_SERVER_ERROR=500;
struct httpd_req_t{int content_len;};
int httpd_resp_send_chunk(httpd_req_t*,const char*,int);int httpd_resp_send_err(httpd_req_t*,int,const char*);int httpd_resp_sendstr(httpd_req_t*,const char*);int httpd_req_get_url_query_str(httpd_req_t*,char*,size_t);int httpd_query_key_value(const char*,const char*,char*,size_t);int httpd_resp_set_type(httpd_req_t*,const char*);int httpd_resp_set_hdr(httpd_req_t*,const char*,const char*);int httpd_req_recv(httpd_req_t*,char*,size_t);
