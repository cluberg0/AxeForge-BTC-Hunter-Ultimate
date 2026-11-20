#!/usr/bin/env python3
"""Update browser regressions for the ONE-TUNER control surface (not old profiles)."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"tests/browser.py"
s=p.read_text()
old="assert not await page.locator('#v2turbo').is_disabled();await page.locator('#tuning .prf button').nth(2).click();assert await page.locator('#tuning [name=pcap]').input_value()=='25';assert len(writes)==n"
new="assert await page.locator('#v2turbo').count()==0;assert await page.locator('#legacyMode').is_hidden();assert await page.locator('[data-legacy-tuner]').is_hidden();assert await page.locator('#turboStart').count()==1;assert await page.locator('#turboPower').count()==1;assert await page.locator('#tuning [name=pcap]').input_value()=='25';assert len(writes)==n"
assert s.count(old)==1
s=s.replace(old,new)
old="dialog_reply['value']='TURBO1000';http_fail['/api/turbo']=400"
new="dialog_reply['value']='FASTSEARCH';http_fail['/api/turbo']=400"
assert s.count(old)==1
s=s.replace(old,new)
s=s.replace('profiles18/22/25W and manually confirmed TURBO1000','ONE-TUNER single-panel UI and manually confirmed FASTSEARCH')
# Exercise the real rendered dashboard and history with a disabled stock tuner.
old="  await page.evaluate('v2render(S)');"
new="""  turbo_saved=copy.deepcopy(turbo);stock_steps=status['tuner']['steps'];status['tuner']['steps']=0
  turbo.update({'armed':True,'state':3,'reason':'power','totalSteps':16,'bestFreq':838,'bestMv':1210,'bestGHs':1670.967,'bestWatts':24.6,'trials':[[650+i*12,1150,1300+i*20,20+i*.2,0] for i in range(16)]})
  await page.evaluate('turboLoad(true)');await page.evaluate('paintTick()')
  assert await page.locator('#tsteps').inner_text()=='16'
  assert await page.locator('#tph').inner_text()=='FASTSEARCH удержание'
  assert '838 МГц @ 1210 мВ' in await page.locator('#tbest').inner_text()
  rows=await page.locator('#turboTrials p').all_text_contents()
  assert len(rows)==16 and rows[0].startswith('650 МГц / 1150 мВ') and rows[-1].startswith('830 МГц / 1150 мВ')
  turbo['totalSteps']=21;turbo['trials']=[[710+i*12,1170,1400+i*20,21+i*.2,0] for i in range(16)]
  await page.evaluate('turboLoad(true)')
  assert await page.locator('#tsteps').inner_text()=='21'
  rows=await page.locator('#turboTrials p').all_text_contents()
  assert len(rows)==16 and rows[0].startswith('710 МГц') and rows[-1].startswith('890 МГц')
  del turbo['totalSteps'];await page.evaluate('turboLoad(true)');await page.evaluate('paintTick()')
  assert await page.locator('#tsteps').inner_text()=='16' # Older API fallback.
  turbo.update({'armed':False,'state':4,'reason':'hardware_power'});await page.evaluate('turboLoad(true)')
  assert 'Аварийный предел мощности' in await page.locator('#turboStatus').inner_text()
  turbo.clear();turbo.update(turbo_saved);status['tuner']['steps']=stock_steps
  await page.evaluate('turboLoad(true)');await page.evaluate('paintTick()')
  print('PASS FASTSEARCH total steps, HOLD and chronological 16-trial history',flush=True)
  await page.evaluate('v2render(S)');"""
assert s.count(old)==1
s=s.replace(old,new)
p.write_text(s)
print('Browser test now verifies no second tuner UI and the same API safeguards')
