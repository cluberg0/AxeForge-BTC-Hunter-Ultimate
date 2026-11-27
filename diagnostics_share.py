#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/"upstream/main/web/index.html"
s=p.read_text()
anchor='<div class="console" id="console"></div>'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''<div class="btns"><button type="button" class="btn" id="hunterDownloadLog">Скачать полный журнал</button></div><p class="note" id="hunterLogStatus" role="status">Журнал текущего запуска (RAM).</p>''')
script=r'''
<script>
document.getElementById('hunterDownloadLog').addEventListener('click',async function(){
 const b=this, status=document.getElementById('hunterLogStatus');
 b.disabled=true;
 try{
 const r=await fetch('/api/logs?since=0',{cache:'no-store'});
 if(!r.ok)throw Error('HTTP '+r.status);
 const d=await r.json();
 if(typeof d.text!=='string')throw Error('Invalid log response');
 // Export only known diagnostic categories; omit credential-bearing lines.
 const lines=d.text.split('\n').filter(x=>/\b(?:turbo|fastsearch|intel|asic|psu|guardian|watchdog|logbuf)\s*:/i.test(x)&&!/password|passwd|token|secret|wallet|authorization|ssid|https?:|stratum\+|bc1[a-z0-9]+/i.test(x));
 const blob=new Blob(['BTC Hunter diagnostic log; current boot; filtered; latest server window\n'+lines.join('\n')],{type:'text/plain;charset=utf-8'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');
 a.href=url;a.download='bitaxe-log-'+Date.now()+'.txt';document.body.appendChild(a);a.click();a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),60000);
 status.textContent='Файл подготовлен. Журнал текущего запуска, диагностические категории.';
 }catch(e){status.textContent='Ошибка загрузки: '+e.message;}finally{b.disabled=false;}
});
</script>
'''
assert s.count('</body>')==1
s=s.replace('</body>',script+'</body>')
p.write_text(s)
(root/"overlay/main/web/index.html").write_text(s)
# Fix fallback allocation: ring indexing always uses RING_SIZE.
p=root/"upstream/main/core/logbuf.cpp"
s=p.read_text()
a='if (!s_ring) s_ring = (char *) malloc(RING_SIZE / 4);'
assert s.count(a)==1
s=s.replace(a,'if (!s_ring) s_ring = (char *) malloc(RING_SIZE);')
a='    portENTER_CRITICAL(&s_mux);\n    uint32_t head = s_head;'
assert s.count(a)==1
s=s.replace(a,'    if (!out || !max) return 0;\n    if (!s_ring) { out[0] = 0; return 0; }\n'+a)
p.write_text(s)
q=root/"overlay/main/core/logbuf.cpp"
q.parent.mkdir(parents=True,exist_ok=True)
q.write_text(s)
print("Fixed log ring allocation and installed current-boot diagnostic export in System")
