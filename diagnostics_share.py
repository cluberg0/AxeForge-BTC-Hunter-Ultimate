#!/usr/bin/env python3
"""Add user-triggered, secret-minimized diagnostics export to existing web UI."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/"upstream/main/web/index.html"
s=p.read_text()
assert s.count("</body>")==1
snippet=r'''
<section class="card" id="hunterDiagnostics" style="margin:12px 0;padding:14px">
 <h3>BTC Hunter · Диагностика</h3>
 <p class="note">Снимок состояния и FASTSEARCH. Системный журнал ESP32 в эту версию экспорта не входит.</p>
 <button type="button" class="btn" id="hunterShareDiagnostics">Отправить диагностический файл</button>
 <p class="note" id="hunterDiagnosticsStatus" role="status"></p>
</section>
<script>
(function(){
 const btn=document.getElementById('hunterShareDiagnostics');
 const status=document.getElementById('hunterDiagnosticsStatus');
 const allow=['hashRate','hashrate','asicGHs','power','voltage','frequency','coreVoltage','temp','vrTemp','fanRpm','uptime','chipTemp','bestFreq','bestMv','bestGHs','bestWatts','persisted','storageError','state','reason','armed','effectivePower','budgetReason','appliedFreq','totalSteps'];
 function sanitize(obj,depth=0){
   if(depth>5)return null;
   if(Array.isArray(obj))return obj.slice(0,100).map(x=>sanitize(x,depth+1));
   if(!obj||typeof obj!=='object')return obj;
   const out={};
   for(const k of allow)if(Object.prototype.hasOwnProperty.call(obj,k))out[k]=sanitize(obj[k],depth+1);
   return out;
 }
 async function snapshot(){
   const out={schema:1,kind:'BTC Hunter diagnostic snapshot (not device event log)',capturedAt:new Date().toISOString(),fastsearch:null,status:null,errors:[]};
   try{if(typeof turboData!=='undefined'&&turboData)out.fastsearch=sanitize(turboData);}catch(e){out.errors.push('FASTSEARCH unavailable');}
   try{
     const c=new AbortController();const timer=setTimeout(()=>c.abort(),5000);
     try{
       const r=await fetch('/api/status',{cache:'no-store',signal:c.signal});
       if(!r.ok)throw Error('HTTP '+r.status);
       out.status=sanitize(await r.json());
     }finally{clearTimeout(timer);}
   }catch(e){out.errors.push('Status request failed: '+String(e.message||e).slice(0,100));}
   return out;
 }
 btn.addEventListener('click',async()=>{
   btn.disabled=true;status.textContent='Подготовка файла…';
   try{
     const data=await snapshot();
     const name='btc-hunter-diagnostics-'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';
     const file=new File([JSON.stringify(data,null,2)],name,{type:'application/json'});
     if(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]})){
       status.textContent='Выберите приложение для отправки';
       await navigator.share({files:[file],title:'BTC Hunter диагностика'});
     }else{
       const url=URL.createObjectURL(file);
       const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();
       setTimeout(()=>URL.revokeObjectURL(url),60000);
       status.textContent='Файл сохранён. Отправьте его через меню «Поделиться».';
     }
   }catch(e){status.textContent=e&&e.name==='AbortError'?'Отправка отменена':'Ошибка: '+String(e.message||e);}
   finally{btn.disabled=false;}
 });
})();
</script>
'''
s=s.replace("</body>",snippet+"\n</body>")
p.write_text(s)
(root/"overlay/main/web/index.html").write_text(s)
print("Diagnostics share button installed (snapshot only; no secret settings or event logs)")
