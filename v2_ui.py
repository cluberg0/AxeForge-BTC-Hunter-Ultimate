#!/usr/bin/env python3
"""2.0 presentation layer; consumes real APIs, never writes tuning on load."""
from pathlib import Path
p=Path('overlay/main/web/index.html');s=p.read_text()
s=s.replace('BTC Hunter ULTIMATE','BTC Hunter ULTIMATE 2.0').replace('BTC HUNTER <span','BTC HUNTER ULTIMATE 2.0 <span')
# Four explicit profiles. TURBO is unavailable until real hardware validation.
s=s.replace('<span>Экономия</span><b>18 Вт</b>','<span>ECO</span><b>18 Вт</b>').replace('<span>Баланс</span><b>22 Вт</b>','<span>BALANCED</span><b>22 Вт</b>')
s=s.replace('<span>Максимум</span><b>30 Вт</b>','<span>BTC HUNTER</span><b>25 Вт</b></button><button type="button" class="btn alt" id="v2turbo" disabled title="30 Вт не проверены на физическом Gamma"><span>TURBO · заблокирован</span><b>до 30 Вт</b>')
s=s.replace('{freq:690,mv:1150,pcap:30}', '{freq:690,mv:1150,pcap:25}').replace('30 Вт — предел БП.','TURBO недоступен: допустимость 30 Вт на этом устройстве не подтверждена.').replace("+(i==2?' БП без запаса.':'')", "+(i==2?' Лимит 25 Вт.':'')")
s=s.replace('<section id="dash" class="on">','''<section id="dash" class="on"><div class="card mb v2hero"><div class="v2eyebrow">BTC HUNTER / ULTIMATE 2.0</div><div class="v2values"><div><small>ASIC · физический счётчик</small><b id="v2asic">—</b></div><div><small>Принятая работа · V1</small><b id="v2useful">—</b></div></div><svg id="v2graph" viewBox="0 0 600 145" role="img" aria-label="Хешрейт ASIC и оценка принятой работы"></svg><p class="note">Голубой — ASIC, янтарный — оценка принятой работы за время загрузки, включая простои. Это разные методы; пропуски не заменяются нулями. График накапливается на открытой странице.</p><p id="v2intel" class="note">AXE Intelligence: ожидаем телеметрию.</p><p id="v2network" class="note">Диагностика сети загружается.</p></div>''')
s=s.replace('</style>','''.v2hero{background:linear-gradient(130deg,#0d1e25,#10131b);border-color:#21414a}.v2eyebrow{font-size:11px;letter-spacing:2px;color:#8cabb4}.v2values{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:20px 0}.v2values small{display:block;color:var(--dim);font-size:11px}.v2values b{display:block;font-size:clamp(20px,5vw,34px);color:#49d4e4;margin-top:8px}.v2values>div+div b{color:#f0b85c}#v2graph{width:100%;height:145px}.v2hero .note{font-size:11px;line-height:1.55}.prf{grid-template-columns:repeat(2,minmax(0,1fr))}#v2turbo{opacity:.45;cursor:not-allowed}#v2clockinput{max-width:130px}</style>''',1)
# Preserve old settings fields/API for backups, hide controls for removed services.
s=s.replace('function a8sample(s){','function a8sample(s){v2render(s);')
# Browser update checks must not make unrelated external requests.
a=s.index('async function checkUpdate(cur){');b=s.index('\n',s.index('const nv=verNum(r.tag);',a));s=s[:a]+'async function checkUpdate(cur){} // manual firmware updates only\n'+s[b:]
# Check only once explicitly. GET status never starts an external request.
s=s.replace('id="guardianenable" disabled','id="guardianenable" disabled')
s=s.replace('<p class="note">Отдельная проверка mempool.space','<button type="button" class="btn alt sm" id="v2guardiancheck" onclick="v2guardianCheck()">Проверить сейчас</button><p class="note">Только ручной запрос. Отдельная проверка mempool.space')
# Add timezone control without altering saved city/credentials or the old API.
s=s.replace('<section id="clock">','<section id="clock"><div class="card mb"><h3>Часы без облачной погоды</h3><p class="note">NTP сохранён. Укажите UTC-смещение вручную; Уссурийск: 600 минут (UTC+10). Город в старых настройках сохранён.</p><label>Смещение UTC, минуты</label><input id="v2clockinput" type="number" min="-720" max="840" step="15"><button type="button" class="btn alt sm" onclick="v2clockSave()">Сохранить время</button></div>')
s=s.replace("if(!document.hidden){a10refresh();hunterRefresh();guardianRefresh()}","if(!document.hidden&&(cur==='dash'||cur==='tuning')){a10refresh();hunterRefresh();if(cur==='dash')guardianRefresh()}")
s=s.replace("setInterval(()=>{if(!document.hidden)tick()},2000)","setInterval(()=>{if(!document.hidden)tick()},5000)")
js=r'''
let v2net=null,v2poll=0,v2busy=false,v2points=[],v2lastSecond=-1;
async function v2load(){if(v2busy||document.hidden||Date.now()-v2poll<15000)return;v2poll=Date.now();v2busy=true;try{const d=await readJson('/api/network');if(d.version!==2||!Array.isArray(d.pools))throw Error();v2net=d;const input=$('v2clockinput');if(input&&document.activeElement!==input)input.value=d.utcOffsetMinutes;}catch(e){v2net=null}finally{v2busy=false}}
function v2render(s){
 if(document.hidden)return;
 if(cur==='dash'||cur==='network'||cur==='clock')v2load();
 const d=typeof hunterData==='undefined'?null:hunterData,secs=+d?.seconds||0,accepted=(d?.pools||[]).reduce((a,p)=>a+(+p.accepted||0),0),work=(d?.pools||[]).reduce((a,p)=>a+(Number.isFinite(p.work)?p.work:0),0);
 const asic=Number.isFinite(s.hashrate)&&s.hashrate>=0&&s.hashrate<=4000?s.hashrate/1000:null,useful=secs>=300&&accepted>=100?work*4294967296/secs/1e12:null;
 $('v2asic').textContent=asic===null?'—':asic.toFixed(2)+' TH/s';$('v2useful').textContent=useful===null?'Накопление':useful.toFixed(2)+' TH/s';
 const caps={18:'ECO',22:'BALANCED',25:'BTC HUNTER'},cap=+cfg.pcap,profile=caps[cap]||'Пользовательский';
 $('v2intel').textContent='AXE Intelligence · '+(s.tuner?.note||s.tuner?.phase||s.status||'ожидание')+' · '+(s.freq??'—')+' МГц / '+(s.coreMv??'—')+' мВ · '+profile+' · эффективный лимит '+(cap>0?Math.min(25,cap):25)+' Вт · ASIC '+(s.chipTemp??s.temp??'—')+'°C / VRM '+(s.vrTemp??'—')+'°C';
 if(d&&secs!==v2lastSecond){v2lastSecond=secs;v2points.push([Date.now(),asic,useful]);if(v2points.length>120)v2points.shift()}
 const values=v2points.flatMap(p=>p.slice(1)).filter(Number.isFinite),max=values.length?Math.max(.1,...values)*1.1:1;let svg='';
 for(let j=0;j<4;j++){let y=15+j*35;svg+=`<line x1="0" x2="600" y1="${y}" y2="${y}" stroke="#21313c"/>`}
 for(const [index,color]of [[1,'#49d4e4'],[2,'#f0b85c']]){let path='',open=false;for(let i=0;i<v2points.length;i++){const v=v2points[i][index];if(!Number.isFinite(v)||(i&&v2points[i][0]-v2points[i-1][0]>45000))open=false;if(!Number.isFinite(v))continue;path+=(open?'L':'M')+(10+i*580/Math.max(1,v2points.length-1)).toFixed(1)+','+(130-v/max*110).toFixed(1);open=true}svg+=`<path data-v2-series="${index}" d="${path}" fill="none" stroke="${color}" stroke-width="2"/>`}
 $('v2graph').innerHTML=svg;
 $('v2network').textContent=v2net?'Network Guardian · переподключений '+v2net.pools.reduce((a,p)=>a+p.reconnects,0)+' · сетевых ошибок '+v2net.pools.reduce((a,p)=>a+p.connectErrors+p.readErrors+p.writeErrors,0)+' · свободно '+Math.round(v2net.freeInternal/1024)+' КБ внутри ESP32 · минимум '+Math.round(v2net.minimumInternal/1024)+' КБ':'Network Guardian: нет данных';
 for(const id of ['wxt','mpheight']){const node=$(id);if(node)node.closest('.card').style.display='none'}
 for(const name of ['city','mempool','mpurl']){const node=document.querySelector('#clock [name="'+name+'"]');if(node){node.disabled=true;node.title='Фоновый сервис отключён в Ultimate2.0'}}
 $('v2turbo').disabled=true;const auto=$('autoupd');if(auto){auto.disabled=true;auto.title='В2.0 только ручная OTA'}
 $('v2guardiancheck').disabled=!guardianData?.enabled||guardianBusy||guardianCommandBusy;
}
async function v2clockSave(){const value=+$('v2clockinput').value;if(!Number.isInteger(value)||value< -720||value>840)return toast('Неверное смещение UTC');try{const r=await fetch('/api/network',{method:'POST',body:JSON.stringify({utcOffsetMinutes:value})});if(!r.ok)throw Error(await r.text());toast('Смещение времени сохранено');v2poll=0;await v2load()}catch(e){toast('Не удалось: '+e.message)}}
async function v2guardianCheck(){if(!guardianData?.enabled||guardianCommandBusy)return;guardianCommandBusy=true;try{const r=await fetch('/api/guardian',{method:'POST',body:JSON.stringify({enabled:true})});if(!r.ok)throw Error(await r.text());toast('Ручная проверка запрошена')}catch(e){toast('Ошибка проверки: '+e.message)}finally{guardianCommandBusy=false}}
'''
anchor='a8init();loadCfg();tick();';assert s.count(anchor)==1;s=s.replace(anchor,js+'\n'+anchor)
p.write_text(s)
