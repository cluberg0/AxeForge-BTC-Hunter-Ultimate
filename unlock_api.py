#!/usr/bin/env python3
import json,pathlib,sys,yaml
r=pathlib.Path(__file__).resolve().parent
p=r/'overlay/docs/native-api.json';j=json.loads(p.read_text());t=j['paths']['/api/turbo'];g=t['get']['responses']['200']['content']['application/json']['schema'];props=g['properties']
for k in ['activeMaxFreq','userMaxPower','psuWatts','psuAmps','powerReserve','inputMargin','appliedFreq','bestFreq','bestMv','bestGHs','bestWatts']:props[k]={'type':'number','minimum':0}
props['unlocked']={'type':'boolean'};props['budgetReason']={'type':'string'};props['trials']={'type':'array','maxItems':16,'items':{'type':'array','items':{'type':'number'}}}
post=t['post']['requestBody']['content']['application/json']['schema'];post.pop('required',None);post['properties']['maxFreq'].pop('multipleOf',None)
post['properties'].update({'action':{'type':'string','enum':['configure']},'psuWatts':{'type':'number','minimum':15,'maximum':120},'psuAmps':{'type':'number','minimum':3,'maximum':24}})
t['post']['summary']='Configure declared PSU/search limits or explicitly start/stop in stock tuner; activation not persisted'
p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
if len(sys.argv)>1:
 u=pathlib.Path(sys.argv[1]);p=u/'docs/openapi.yaml';full=yaml.safe_load(p.read_text());full['paths']['/api/turbo']=t
 def visit(v):
  if isinstance(v,dict):
   for k,w in list(v.items()):
    if k=='limits'and isinstance(w,dict)and 'maxFreq'in w.get('properties',{}):w['properties'].update({'boardMaxPower':{'type':'number'},'effectivePower':{'type':'number'}})
    visit(w)
  elif isinstance(v,list):
   for w in v:visit(w)
 visit(full);p.write_text(yaml.safe_dump(full,sort_keys=False,allow_unicode=True));(u/'docs/native-api.json').write_bytes((r/'overlay/docs/native-api.json').read_bytes())
