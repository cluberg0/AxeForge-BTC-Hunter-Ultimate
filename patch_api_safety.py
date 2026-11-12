#!/usr/bin/env python3
"""Apply bounded OTA receives, safe NVS allocation and the native API reference."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent


def patch(root):
    replacements = {
        'main/core/settings.cpp': [(
            '''        char *json = (char *) malloc(len);
        nvs_get_str(h, "pools", json, &len);
        pools_from_json(json);
        free(json);''',
            '''        // Stored data can be damaged or unavailable under memory pressure.
        // Keep defaults in RAM and leave the saved namespace untouched on error.
        char *json = (char *) malloc(len);
        if (json) {
            if (nvs_get_str(h, "pools", json, &len) == ESP_OK) pools_from_json(json);
            else ESP_LOGW(TAG, "saved pools unreadable; keeping defaults (no erase)");
            free(json);
        } else {
            ESP_LOGE(TAG, "not enough memory to load saved pools (no erase)");
        }''')],
        'main/net/web.cpp': [(
            '''    int remaining = req->content_len;
    bool ok = true;
    while (remaining > 0) {
        int n = httpd_req_recv(req, buf, remaining < CHUNK ? remaining : CHUNK);
        if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;''',
            '''    int remaining = req->content_len;
    bool ok = true;
    int receive_timeouts = 0;
    while (remaining > 0) {
        int n = httpd_req_recv(req, buf, remaining < CHUNK ? remaining : CHUNK);
        // Abandoned iPhone uploads must release the HTTP task and OTA handle.
        // Allow temporary Wi-Fi stalls; three consecutive 15-second timeouts abort.
        if (n == HTTPD_SOCK_ERR_TIMEOUT) {
            if (++receive_timeouts < 3) continue;
            ok = false;
            break;
        }
        receive_timeouts = 0;''')],
    }
    for rel, edits in replacements.items():
        p = root / rel
        s = p.read_text()
        for old, new in edits:
            assert s.count(old) == 1, (rel, 'expected one unpatched source anchor')
            s = s.replace(old, new)
        p.write_text(s)
    doc = json.loads((ROOT / 'overlay/docs/native-api.json').read_text())
    spec = root / 'docs/openapi.yaml'
    s = spec.read_text()
    for path, methods in doc['paths'].items():
        assert '\n  ' + path + ':' not in s, ('already documented', path)
        s += '\n  ' + path + ':\n'
        for method, body in methods.items():
            s += '    ' + method + ': ' + json.dumps(body, ensure_ascii=False) + '\n'
    spec.write_text(s)
    print('OTA/NVS safety and native API documentation applied')


if __name__ == '__main__':
    patch(pathlib.Path(sys.argv[1]).resolve())
