from pathlib import Path
import re
root=Path(__file__).resolve().parent
s=(root/'base-ui.html').read_text()
def replace(old,new):
 global s
 assert s.count(old)==1,(old[:100],s.count(old));s=s.replace(old,new)
def cut(a,b,new):
 global s
 i=s.index(a);j=s.index(b,i);s=s[:i]+new+'\n'+s[j:]
replace('RU-FIX 9\';','RU-FIX 10 NATIVE\';')
replace('Архив хранится в этом браузере; при закрытии страницы данные не собираются.','Архив ведётся майнером без Safari. Час: 30 с; сутки: 5 мин (после перезапуска — часовые данные); 7 дней: час; 30 дней: сутки. Неполные интервалы возможны.')
replace('Оценка по замерам Safari. Помощник не меняет частоту или напряжение. Ориентир заполняет стартовые поля, затем нужен ваш выбор «Сохранить разгон».','Анализ выполняется на ESP32 круглосуточно. Режим запоминается автоматически после 30 минут устойчивой работы. Возврат доступен только при неудачном окне штатного автотюнера и не повышает частоту или напряжение.')
replace('<button class="btn alt sm" id="a8remember" disabled onclick="a8remember()">Запомнить режим</button>','<button class="btn alt sm" id="a8remember" disabled onclick="a8remember()">Архив ESP32</button>')
replace('onchange="a8period=+this.value;a8draw()"','onchange="a8period=+this.value;a8draw();a10refresh(true)"')
replace('Автоподъём только при открытой странице и стабильном майнинге: два замера, не чаще 10 мин, только повышение минимума. Не снижает обдув и не меняет напряжение. При скрытии страницы выключается. Аварийные защиты штатные.','Автономная кривая работает даже без телефона. Она повышает фактический обдув относительно штатного алгоритма, не меняя сохранённый минимум и не вмешиваясь в ручной режим. Возврат к устойчивой точке включается отдельно. Защиты штатные.')
replace('<button class="btn alt sm" type="button" id="a8fanbtn" onclick="a8toggle()">Разрешить автоподъём</button>','<button class="btn alt sm" type="button" id="a8fanbtn" onclick="a8toggle()" disabled>Загрузка…</button><button class="btn alt sm" type="button" id="a10rollback" onclick="a10toggleRollback()" disabled>Загрузка…</button><button class="btn alt sm" type="button" id="a10save" onclick="a10save()" disabled>Сохранить кривую</button>')
cut('function a8sample(s)', 'function a8draw()', '''let a10info=null,a10cache={},a10busy=false,a10last=0,a10dirty=false,a10commandBusy=false;
async function a10refresh(force=false){if(a10busy||(!force&&Date.now()-a10last<60000))return;a10busy=true;a10last=Date.now();try{for(const sec of [...new Set([3600,a8period,86400])]){const d=await readJson('/api/intelligence?range='+sec);if(!d.native||!Array.isArray(d.rows))throw Error('bad archive');a10info=d;a10cache[sec]=d.rows.filter(a8valid);if(!a10dirty&&Array.isArray(d.curve))for(let i=0;i<4;i++)$('a8c'+i).value=d.curve[i];}a8cool(S,false);a8analytics(S);a8draw()}catch(e){a10info=null;a8cool(S,false);$('a8advice').textContent='Архив ESP32 недоступен. Штатный майнинг работает независимо.';$('a8recall').disabled=true;}finally{a10busy=false;a8cool(S)}}
function a8sample(s){a8lastStatus=Date.now();if(!document.hidden)a10refresh()}
function a8range(sec){const now=Date.now(),period=sec<=3600?3600:sec;return (a10cache[period]||[]).filter(r=>r[0]>=now-sec*1000&&r[0]<=now+30000).map(r=>{if(r[1]===null||!hashOK(r[1]*1000)){const q=r.slice();q[1]=q[5]=null;return q}return r})}
function a8avg(a,j){const p=a.filter(r=>Number.isFinite(r[j]));const n=p.reduce((x,r)=>x+(r[18]||1),0);return n?p.reduce((x,r)=>x+r[j]*(r[18]||1),0)/n:null}
''')
replace("(a8storage?'архив Safari':'память недоступна')+' · шаг 1–5 мин'", "(a10info?.archiveOk?'архив ESP32':'архив / проверка памяти')+' · '+({3600:'30 с',86400:'5 мин / 1 ч',604800:'1 ч',2592000:'1 сутки'}[a8period])")
replace('r[0]-last>(now-r[0]>864e5?360000:120000)','r[0]-last>Math.max(90,(r[19]||30)*1.5,(lastStep||30)*1.5)*1000')
i=s.index('function a8draw()');s=s[:i]+s[i:].replace('avg:p.reduce((a,b)=>a+b,0)/p.length','avg:a8avg(A.filter(r=>Number.isFinite(value(r))),j)',1)
replace('function a8csv(){const a=a8range(2592000);','function a8csv(){const a=a8range(a8period);')
replace("'Время UTC;Монета;'+A8N", "'Время UTC;Монета;Замеров;Интервал (с);'+A8N")
replace("+(r[17]||'')+';'+A8J", "+(r[17]||'')+';'+(r[18]||1)+';'+(r[19]||30)+';'+A8J")
i=s.index('function a8draw()');s=s[:i]+s[i:].replace('let seg=[],last=0;','let seg=[],last=0,lastStep=30;',1).replace('last=r[0]}flush()','last=r[0];lastStep=r[19]||30}flush()',1)
# Keep original warnings and odds; replace UI-only stable decision.
start=s.index('function a8analytics(s)');i=s.index('const warnings=[];',start);s=s[:start]+"function a8analytics(s){const ok=!!a10info&&a10info.stableSamples>=61;const warnings=[];"+s[i+len('const warnings=[];'):]
replace("const prev=a8saved?.point;", "const p0=a10info?.point;const prev=p0?.[0]?[p0[0],p0[1],p0[3]/1000]:null;")
replace('Режим устойчив по доступным замерам. Можно сохранить ориентир.','Режим устойчив по замерам ESP32. Ориентир сохраняется автоматически.')
replace('Режим найден. Собираем замеры за 30 минут.','Режим найден. ESP32 проверяет стабильность за 30 минут.')
i=s.index("$('a8remember').disabled=!ok");j=s.index('\n if(a8actual)',i)
s=s[:i]+"$('a8remember').disabled=true;$('a8recall').disabled=!a10info?.point?.[0]||!cfgReady;$('a8saved').textContent=a10info?.point?.[0]?'Ориентир ESP32: '+a10info.point[0]+' МГц / '+a10info.point[1]+' мВ · '+a8num(a10info.point[3]/1000)+' TH/s':'Ориентир ещё не сохранён';if(a10info&&!a10info.archiveOk)$('a8saved').textContent+=' · Ошибка записи flash; проверьте журнал.';"+s[j:]
cut('function a8remember()', 'function a8stage(', "function a8remember(){toast('Ориентир сохраняет ESP32 автоматически')}")
cut('function a8recall()', 'function a8curve()', '''function a8recall(){const p=a10info?.point;if(!p?.[0]||!cfgReady||p[0]>cfg.limits.maxFreq||p[1]<cfg.limits.minMv||p[1]>cfg.limits.maxMv||p[2]<1||p[2]>30)return toast('Нет допустимого ориентира');a8stage({freq:p[0],mv:p[1],pcap:p[2],atune:true,tgoal:1,chiptune:false})}''')
cut('function a8toggle()', 'function a8poolDelete()', '''async function a10save(enabled=a10info?.enabled,restore=a10info?.restore){if(!a10info||!cfgReady||a10busy||a10commandBusy)return toast('Нет связи с ESP32');const curve=a8curve();if(curve.some((v,i)=>i&&v<curve[i-1]))return toast('Кривая должна возрастать');if(!confirm('Сохранить автономную кривую и режим возврата? Штатные защиты остаются включены.'))return;a10commandBusy=true;a8cool(S);try{const r=await fetch('/api/intelligence',{method:'POST',body:JSON.stringify({enabled:!!enabled,restore:!!restore,curve})});if(!r.ok)throw Error(await r.text());a10dirty=false;await a10refresh(true);toast('Настройки ESP32 сохранены')}catch(e){toast('Не удалось сохранить: '+e.message)}finally{a10commandBusy=false;a8cool(S)}}
function a8toggle(){if(a10info)a10save(!a10info.enabled,a10info.restore)}
function a10toggleRollback(){if(a10info)a10save(a10info.enabled,!a10info.restore)}
function a8cool(s){const need=a8fanNeed(s);$('a8fantext').textContent='Кривая: '+(need===null?'нет данных':need+'%')+' · оба датчика. Фактический обдув не ниже штатного.';for(const id of ['a8fanbtn','a10rollback','a10save'])$(id).disabled=!a10info||!cfgReady||a10commandBusy||a10busy;$('a8fanbtn').textContent=a10info?.enabled?'Автообдув: вкл.':'Автообдув: выкл.';$('a10rollback').textContent=a10info?.restore?'Возврат: вкл.':'Возврат: выкл.';}
''')
replace("setInterval(a8stale,2000)}", "setInterval(a8stale,2000);document.querySelectorAll('[id^=a8c]').forEach(e=>{if(/^a8c[0-3]$/.test(e.id))e.addEventListener('input',()=>a10dirty=true)});}")
# no stale browser archive allocation
replace("let a8hist=a8get('hist',[])","let a8hist=[]")
# hide obsolete toggle scripts, which never turn on in native mode, but leave existing visual behavior
(root/'overlay/main/web').mkdir(parents=True,exist_ok=True)
(root/'overlay/main/web/index.html').write_text(s)
