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
# Exercise the real render path with an active, safe tuner and failed storage.
old="  await page.locator('#turboStop').click();"
new="""  await page.evaluate("turboData.persisted=false;turboData.storageError=4357;turboRender()")
  assert 'результат не сохранён' in await page.locator('#turboStatus').inner_text()
  assert '4357' in await page.locator('#turboStatus').inner_text()
  assert not await page.locator('#turboStop').is_disabled()
  await page.locator('#turboStop').click();"""
assert s.count(old)==1
s=s.replace(old,new)
p.write_text(s)
print('Browser test now verifies no second tuner UI and the same API safeguards')
