#!/usr/bin/env python3
from pathlib import Path
import sys
p=Path(sys.argv[1])/"upstream/main/web/index.html"
s=p.read_text()
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:60],s.count(a))
 s=s.replace(a,b,1)
patch("if(prompt('Ручной эксперимент с прогревом, повторными измерениями и откатом. Введите TURBO1000.')!=='TURBO1000')","if(prompt('FASTSEARCH: поиск с автоматическим безопасным откатом. Введите FASTSEARCH.')!=='FASTSEARCH')")
patch("toast('TURBO: '+e.message)","toast('FASTSEARCH: '+e.message)")
patch('TURBO API недоступен','FASTSEARCH API недоступен')
patch("[L.maxPower+' Вт','Пользовательский максимум']","[L.maxPower+' Вт','Программный защитный максимум']")
patch('<p class="info" id="turboStatus">Загрузка статуса…</p>','<p class="info" id="turboStatus">Загрузка статуса…</p><p class="note" id="onePowerNote">Ожидание номинала БП…</p>')
patch("else $('turboStatus').textContent='FASTSEARCH API недоступен';",
 """else $('turboStatus').textContent='FASTSEARCH API недоступен';
 $('onePowerNote').textContent=d
 ? 'Номинал БП '+d.psuWatts+' Вт / '+d.psuAmps+' А; ваш запрос '+d.requestedPower+' Вт; реально доступно '+d.effectivePower+' Вт. Резерв БП обязателен. '+(budgetReasons[d.budgetReason]||d.budgetReason)
 : 'Нет данных о питании: разгон недоступен.';""")
patch("$('tsteps').textContent=t.steps;",
 """$('tsteps').textContent=t.steps;
if(turboData?.available){
 const x=turboData;
 $('tph').textContent=x.armed?(x.state===3?'FASTSEARCH удержание':'FASTSEARCH поиск'):'FASTSEARCH пауза';
 $('tbest').textContent=x.bestFreq?x.bestFreq+' МГц @ '+x.bestMv+' мВ ('+(x.bestGHs/1000).toFixed(3)+' TH/s)':'Нет подтверждённого режима';
 if(!x.armed)$('tnote').textContent='Штатный автотюнер отключён. Причина: '+(turboReasons[x.reason]||x.reason);
}""")
p.write_text(s)
print("Dashboard and power budget now show one FASTSEARCH engine")
