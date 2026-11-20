#!/usr/bin/env python3
"""V3 NVS persistence repair: diagnostic error codes, safe retry, no needless abort."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);p=root/'upstream/main/core/turbo.cpp';s=p.read_text()
old='''bool save(){
 nvs_stats_t st{};if(nvs_get_stats(nullptr,&st)!=ESP_OK||st.free_entries<128+(sizeof(archive)+31)/32+4)return false;
 nvs_handle_t h;if(nvs_open("af_turbo",NVS_READWRITE,&h)!=ESP_OK)return false;
 bool good=nvs_set_blob(h,"map",&archive,sizeof(archive))==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);return good;
}'''
new='''std::atomic<int> storage_error{0};
bool save(){
 // NVS uses variable-length blobs and page compaction. The old global
 // free_entries >= 128 + blob size gate falsely rejected healthy partitions.
 // Let NVS itself decide whether space is sufficient.
 nvs_handle_t h;
 esp_err_t e=nvs_open("af_turbo",NVS_READWRITE,&h);
 if(e!=ESP_OK){storage_error=int(e);ESP_LOGE("turbo","NVS open: %s",esp_err_to_name(e));return false;}
 e=nvs_set_blob(h,"map",&archive,sizeof(archive));
 if(e==ESP_OK)e=nvs_commit(h);
 nvs_close(h);
 storage_error=int(e);
 if(e!=ESP_OK)ESP_LOGE("turbo","NVS archive save: %s",esp_err_to_name(e));
 return e==ESP_OK;
}'''
assert s.count(old)==1,s.count(old);s=s.replace(old,new)
old='persisted=save();if(!persisted){stop(Reason::Storage);return false;}return true;'
new='''persisted=save();
 // Flash persistence failure is NOT an ASIC, PSU or thermal failure.
 // Keep mining and keep the measured point in RAM, but report persisted=false.
 // A reboot may lose this point until flash storage succeeds.
 if(!persisted)ESP_LOGW("turbo","NVS save failed, continuing with volatile measurement");
 return true;'''
assert s.count(old)==1;s=s.replace(old,new)
p.write_text(s)
print("V3 NVS: removed false free-space gate, logged ESP errors, no unsafe storage abort")
