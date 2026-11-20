#!/usr/bin/env python3
"""Bounded NVS archive. Keep legacy map read-only and preserve settings namespaces."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/"upstream/main/core/turbo.cpp"
s=p.read_text()
def once(a,b):
 global s
 n=s.count(a)
 assert n==1,(a[:90],n)
 s=s.replace(a,b,1)
once('std::atomic<int> storage_error{0};',"""// Small, versioned archive: avoids writing the full in-RAM history to NVS.
struct CompactArchive {
 uint32_t magic=0x43545034;
 Point points[4]{};
};
std::atomic<int> storage_error{0};""")
once('e=nvs_set_blob(h,"map",&archive,sizeof(archive));',"""CompactArchive compact{};
 // Save up to four strongest *verified* historic modes, ordered by hashrate.
 // Never persist short probes, and never touch the Wi-Fi/pool/settings namespaces.
 for(const auto &pt:archive.points){
   if(!turbo_math::valid(pt))continue;
   for(unsigned j=0;j<4;j++){
     if(pt.ghs>compact.points[j].ghs){
       for(unsigned k=3;k>j;k--)compact.points[k]=compact.points[k-1];
       compact.points[j]=pt;
       break;
     }
   }
 }
 e=nvs_set_blob(h,"map_v4",&compact,sizeof(compact));""")
# On boot, accept legacy archive first; prefer a validated compact archive when present.
anchor='  Config c;n=sizeof(c);e=nvs_get_blob(h,"config",&c,&n);'
replacement="""  CompactArchive compact{};n=sizeof(compact);
  esp_err_t compact_err=nvs_get_blob(h,"map_v4",&compact,&n);
  if(compact_err==ESP_OK){
    bool valid=n==sizeof(compact)&&compact.magic==0x43545034;
    if(valid)for(const auto &pt:compact.points)
      if(pt.mhz&&!turbo_math::valid(pt)){valid=false;break;}
    if(valid){
      archive=Archive{};
      for(unsigned i=0;i<4;i++)archive.points[i]=compact.points[i];
      persisted=true;storage_error=0;
    }else load_error(ESP_FAIL);
  }else if(compact_err!=ESP_ERR_NVS_NOT_FOUND)load_error(compact_err);
  Config c;n=sizeof(c);e=nvs_get_blob(h,"config",&c,&n);"""
once(anchor,replacement)
p.write_text(s)
# The native test compiles the same source used by the device.
overlay=root/"overlay/main/core/turbo.cpp"
overlay.write_text(s)
print("V4 compact archive: 4 verified points, legacy read-only, no NVS erase")
