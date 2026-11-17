#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/"upstream/main/web/index.html"
s=p.read_text()
def replace(a,b):
 global s
 assert s.count(a)==1,(a[:50],s.count(a))
 s=s.replace(a,b,1)
a=s.index('<div class="card"><h3>Профили мощности</h3>')
b=s.index('<div class="card"><h3>Режим</h3>',a)
s=s[:a]+s[b:]
replace('<div class="card"><h3>Режим</h3>','<div class="card" id="legacyMode" style="display:none"><h3>Legacy settings</h3>')
replace('<div id="pcaprow"><label>Лимит мощности (Вт)</label><input id="turboPower" name="pcap" type="number" min="0" max="2000" step="1" placeholder="Лимит платы"></div>','')
replace('<div><label>Номинальная мощность БП, Вт</label>','<div id="pcaprow"><label>Потолок платы (Вт)</label><input id="turboPower" name="pcap" type="number" min="18" max="30" step="1"></div><div><label>Номинальная мощность БП, Вт</label>')
replace('<div class="card"><h3>Запас разгона','<div class="card" style="display:none" data-legacy-tuner="hidden"><h3>Запас разгона')
replace('''<div class="btns"><button class="btn">Сохранить разгон</button><button type="button" class="btn alt" onclick="act('/api/retune')">Начать / перезапустить поиск</button></div>''','<div class="btns"><button class="btn">Сохранить настройки</button></div>')
replace('<h3>Автонастройка</h3>','<h3>FASTSEARCH · один автотюнер</h3>')
replace('<h3>Разблокировка разгона <span class="tag" id="ocst">','<h3>FASTSEARCH · управление <span class="tag" id="ocst">')
replace('<h3>Автоматический поиск TURBO1000</h3>','<h3>Параметры FASTSEARCH</h3>')
replace('Ручную частоту и лимит мощности задавайте в единственной штатной форме выше. Разблокировка сохраняется; запуск поиска — отдельное действие.','Один автоматический поиск частоты и напряжения. Параметры питания задаются здесь.')
replace('Более мощный БП не поднимает пользовательский предел выше 30 Вт.','БП 5 В / 6 А рассчитан на 30 Вт номинально. Контроллер оставляет запас и не допускает превышения физического бюджета.')
replace('Подтвердить и начать</button>','Запустить FASTSEARCH</button>')
replace('Остановить и вернуть штатный режим</button>','Остановить и безопасно снизить частоту</button>')
replace('Перезагрузка сохраняет разрешение и БП, но не запускает эксперимент; сохранённая частота выше штатной возвращается к безопасной стартовой точке до ручного подтверждения.','При загрузке поиск запускается автоматически, если датчики, сеть и питание исправны.')
assert s.count('id="turboPower"')==1
assert s.count('id="turboStart"')==1
assert s.count('id="turboStop"')==1
assert s.count('data-legacy-tuner="hidden"')==1
p.write_text(s)
print("ONE-TUNER UI has one visible search card")
