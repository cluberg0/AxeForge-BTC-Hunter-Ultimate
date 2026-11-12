import asyncio,json,pathlib,time,copy,os,shutil
from playwright.async_api import async_playwright
root=pathlib.Path(__file__).resolve().parent.parent;ns=json.loads((root/'tests/browser-fixture.json').read_text())
cfg=ns['cfg'];status=ns['status'];pools=ns['pools'];status['uptime']=36000
html=(root/'overlay/main/web/index.html').read_text();writes=[];opts={'enabled':False,'restore':False,'curve':[50,55,75,100]};fail=False;hunter_fail=False;http_fail={};auth_required=False;login_fail=False;requests=[];hunter_trial={"state":0,"stage":0,"elapsed":0,"rates":[0,0,0],"accepted":[0,0,0],"rejected":[0,0,0]}
async def main():
 global fail,hunter_fail,auth_required,login_fail
 async with async_playwright() as p:
  engine=os.getenv('BROWSER','chromium');b=await (p.webkit.launch() if engine=='webkit' else p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or None,args=['--no-sandbox']));ctx=await b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,accept_downloads=True);page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:print('JS',m.type,m.text) if m.type in ['error','warning'] else None);page.on('dialog',lambda d:d.accept())
  async def mock(source,req):
   global auth_required
   path=req['path'].split('?')[0];requests.append(req)
   if path in http_fail:return {'status':http_fail[path],'body':'simulated failure'}
   if path=='/api/otp' and req['method']=='POST':
    if login_fail:raise RuntimeError('simulated login connection loss')
    auth_required=False;return {'status':200,'body':json.dumps({'token':'test-session'})}
   if auth_required and path=='/api/settings':return {'status':401,'body':'login required'}
   if req['method']=='POST':
    d=json.loads(req.get('body') or '{}');writes.append((path,d));
    if path=='/api/intelligence':
     if fail:return {'status':500,'body':'storage failed'}
     opts.update(d)
    if path=='/api/settings':cfg.update(d)
    if path=='/api/hunter':
     if hunter_fail:return {'status':400,'body':'not stable'}
     hunter_trial['state']=1 if d.get('start') else 3
    return {'status':200,'body':'OK'}
   if path=='/api/hunter':
    obj={'native':True,'taskOk':True,'seconds':3600,'pools':[{'work':1337*900,'btcWork':1337*900,'btcAccepted':900,'accepted':900,'rejected':1,'missing':0,'failed':0,'cleanN':10,'cleanMs':40,'cleanMax':100}]+[{'work':0,'btcWork':0,'btcAccepted':0,'accepted':0,'rejected':0,'missing':0,'failed':0,'cleanN':0,'cleanMs':0,'cleanMax':0} for _ in range(3)],'candidate':{'state':3,'pool':0,'hash':'000000000000000000000000000000000000000000000000000000000000abcd','persisted':True},'trial':hunter_trial}
   elif path=='/api/intelligence':
    sec=int(req['path'].split('=')[-1]);step={3600:30,86400:300,604800:3600,2592000:86400}[sec];now=int(time.time());rows=[]
    for i in range(12):rows.append([(now-(12-i)*step)*1000,3933.24 if i==4 else 1.53+i%3*.01,55,64,23.3,15.1,50,786,1170,.28,148364561003867,None,None,None,5654,5.14,1164,'BTC',1,step])
    obj={'native':True,'time':now,'last':now,'archiveOk':True,'point':[786,1170,25,1530,now],'stableSamples':61,'rows':rows,**opts}
   else:obj={'/api/settings':cfg,'/api/status':status,'/api/pools':pools,'/api/history':{'step':30,'hashrate':[1450,3933240,1550,1530],'temp':[55,56,56,54],'power':[23,24,24,23]},'/api/stats':{'step':300,'hashrate':[1450,1550],'temp':[55,56],'power':[23,24]},'/api/scoreboard':[],'/api/otp':{'enabled':False,'clock':True},'/api/logs':{'next':0,'ms':18478000,'text':''},'/api/selftest':{'running':False,'done':False},'/api/swarm':{'miners':[]},'/api/layout':{'pages':[[],[]]}}.get(path,{})
   return {'status':200,'body':json.dumps(obj,ensure_ascii=False)}
  await page.expose_binding('mockApi',mock)
  pre="""<script>window.mem={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>mem[k]??null,setItem:(k,v)=>mem[k]=String(v),removeItem:k=>delete mem[k]}});window.fetch=async(u,o={})=>{const r=await mockApi({path:String(u),method:o.method||'GET',body:o.body,headers:o.headers||{}});return new Response(r.body,{status:r.status,headers:{'content-type':'application/json'}})};history.replaceState=()=>{};</script>"""
  await page.route('http://axeforge.test/',lambda route:route.fulfill(status=200,content_type='text/html',body=html.replace('<head>','<head>'+pre,1)));await page.goto('http://axeforge.test/');await page.wait_for_function('typeof a10info!=="undefined" && a10info && cfgReady && !a10busy && P.pools.length===4 && hunterData && !hunterBusy',timeout=15000)
  assert not writes, writes;assert not errors,errors
  assert 'Принят пулом, сеть не подтверждена' in await page.locator('#huntercandidate').inner_text()
  assert await page.locator('#odday').inner_text()!='1 из 5,000,000'
  assert '900 / 1' in await page.locator('#hunterstats').inner_text()
  await page.evaluate('tab("tuning")');await page.locator('#hunterstart').click();await page.wait_for_function('hunterData.trial.state===1 && !hunterCommandBusy');assert writes[-1]==('/api/hunter',{'start':True})
  await page.locator('#hunterstop').click();await page.wait_for_function('hunterData.trial.state===3 && !hunterCommandBusy');assert writes[-1]==('/api/hunter',{'start':False})
  hunter_fail=True;await page.locator('#hunterstart').click();await page.wait_for_function('!hunterCommandBusy');assert hunter_trial['state']==3;hunter_fail=False
  assert cfg['jobms']==0 and cfg['pcap']==25
  await page.evaluate('tab("dash");a8pick=A8N.map((_,i)=>i);a8draw()');assert await page.locator('#a8chart [data-a8line]').count()>=12
  assert await page.evaluate('a8range(3600)[4][1]===null');assert '3933' not in await page.locator('#a8legend').inner_text()
  await page.locator('#a8period').select_option('2592000');await page.wait_for_function('a10cache[2592000]?.length===12 && !a10busy');assert await page.locator('#a8chart [data-a8line]').count()>=12
  async with page.expect_download() as dl: await page.locator('button[onclick="a8csv()"]').click()
  assert (await dl.value).suggested_filename.endswith('.csv')
  await page.evaluate('tab("tuning")');await page.locator('#a8fanbtn').click();await page.wait_for_function('a10info?.enabled && !a10busy');assert writes[-1][0]=='/api/intelligence' and writes[-1][1]['enabled'] and cfg['fanmin']==50
  await page.locator('#a10rollback').click();await page.wait_for_function('a10info?.restore && !a10busy');assert writes[-1][1]['restore']
  n=len(writes);await page.evaluate('Promise.all([a10save(),a10save()])');assert len(writes)==n+1
  fail=True;await page.locator('#a8fanbtn').click();await page.wait_for_timeout(200);assert opts['enabled'];fail=False
  await page.evaluate('tab("dash")');await page.locator('#a8recall').click();assert await page.locator('#tuning [name=freq]').input_value()=='786';assert await page.locator('#tuning [name=pcap]').input_value()=='25'
  n=len(writes);await page.locator('#tuning .prf button').last.click();assert await page.locator('#tuning [name=pcap]').input_value()=='30';assert len(writes)==n
  for w in [320,375,390,430,768]:
   await page.set_viewport_size({'width':w,'height':844})
   for t in ['dash','pools','tuning','display','clock','network','system']:
    await page.evaluate(f'tab("{t}")');await page.wait_for_timeout(30);v=await page.evaluate('({w:innerWidth,scroll:document.documentElement.scrollWidth})');assert v['scroll']<=v['w']+2,(w,t,v)
  assert await page.locator('nav button[data-t]').evaluate_all('(els)=>els.map(e=>e.dataset.t)')==['dash','pools','tuning','system']
  for w in [320,375,390,430,768]:
   await page.set_viewport_size({'width':w,'height':844})
   for t in ['display','clock','network','swarm']:
    await page.locator('nav button[data-t=system]').click();await page.locator(f'#system [data-sub={t}]').click()
    assert await page.locator(f'section#{t}').evaluate('(e)=>e.classList.contains("on")')
    assert await page.locator('nav button.on').get_attribute('data-t')=='system'
    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
    await page.locator(f'#{t} .sysback').click();assert await page.locator('#system').evaluate('(e)=>e.classList.contains("on")')
  print('PASS navigation, Hunter, archive, profiles',flush=True)
  # Regression coverage for refused safeguard changes and OTP login recovery.
  await page.evaluate('tab("system")');old_guard=cfg['otaguard'];http_fail['/api/settings']=500
  await page.locator('#otaguard').click();await page.wait_for_function('!document.getElementById("otaguard").disabled')
  assert await page.locator('#otaguard').is_checked()==old_guard
  http_fail.clear();auth_required=True
  pending=asyncio.create_task(page.evaluate('readJson("/api/settings").catch(e=>({error:e.message}))'))
  await page.locator('#login.on').wait_for();await page.locator('#loginno').click();await pending
  await page.wait_for_timeout(1200);assert not await page.locator('#login').evaluate('(e)=>e.classList.contains("on")')
  pending=asyncio.create_task(page.evaluate('readJson("/api/settings")'));await page.locator('#login.on').wait_for()
  login_fail=True;await page.locator('#loginok').click();await page.wait_for_function('document.getElementById("loginerr").textContent.includes("Нет связи")');login_fail=False
  await page.locator('#logincode').fill('123456');await page.locator('#loginok').click();await pending
  assert await page.evaluate('SESS')=='test-session'
  await page.evaluate('fetch("https://external.example/test")');assert requests[-1]['headers']=={},requests[-1]
  print('PASS OTP and failed-save recovery',flush=True)
  http_fail['/api/page']=500;await page.evaluate('pageGo(1)');assert 'Не удалось переключить экран' in await page.locator('#toast').inner_text();http_fail.clear()
  async with page.expect_download() as downloaded:await page.evaluate('backup()')
  backup_file=await (await downloaded.value).path();backup_data=json.loads(pathlib.Path(backup_file).read_text());assert 'limits' not in backup_data['settings'] and 'wpass' not in backup_data['settings']
  before=len(writes);await page.locator('input[type=file][accept=".json"]').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':json.dumps(backup_data).encode()});await page.wait_for_function('!restoreBusy&&!cfgBusy&&cfgReady');assert len(writes)==before+2
  # Every theme moves on the same open page; motion settings and reduced motion stop it.
  shots=root/'dist/screenshots';shots.mkdir(parents=True,exist_ok=True)
  await page.set_viewport_size({'width':390,'height':844});await page.evaluate('tab("dash");setTheme(0);motionUi(true)')
  for theme in ['neon','hole','btc','aurora']:
   await page.locator('#a8bg').select_option(theme,force=True)
   one=await page.evaluate('getComputedStyle(document.getElementById("aurora"),"::before").transform');await page.wait_for_function('(one)=>getComputedStyle(document.getElementById("aurora"),"::before").transform!==one',arg=one,timeout=10000)
   two=await page.evaluate('getComputedStyle(document.getElementById("aurora"),"::before").transform');assert one!=two,(theme,one,two)
  print('PASS live backgrounds',flush=True)
  await page.screenshot(path=str(shots/f'{engine}-390-dashboard.png'),full_page=True,animations='disabled')
  await page.evaluate('motionUi(false)');assert await page.evaluate('getComputedStyle(document.getElementById("aurora"),"::before").animationName')=='none'
  await page.evaluate('motionUi(true)');await page.emulate_media(reduced_motion='reduce');assert await page.evaluate('getComputedStyle(document.getElementById("aurora"),"::before").animationName')=='none'
  await page.emulate_media(reduced_motion='no-preference')
  await page.evaluate('Object.defineProperty(document,"hidden",{get:()=>true,configurable:true});backgroundPower()');assert await page.evaluate('getComputedStyle(document.getElementById("aurora"),"::before").animationPlayState')=='paused'
  await page.evaluate('Object.defineProperty(document,"hidden",{get:()=>false,configurable:true});backgroundPower()')
  for w in [320,375,430]:
   await page.set_viewport_size({'width':w,'height':844});await page.evaluate('tab("system")')
   await page.screenshot(path=str(shots/f'{engine}-{w}-system.png'),full_page=True,animations='disabled')
  # Invalid/empty archives must clear the plot rather than invent zero measurements.
  await page.evaluate('a10cache={};tab("dash");a8draw()');assert await page.locator('#a8chart [data-a8line]').count()==0
  assert 'Нет замеров' in await page.locator('#a8chart').text_content()
  assert not errors,errors
  print('PASS: BTC Hunter stats, candidate state, explicit start/stop and server refusal; PASS: four main tabs and four system subpages via actual clicks, no horizontal overflow; PASS: native API, all graph lines, outlier, monthly range, CSV, independent toggles, refusal, staged recall, profile 30 W, all original sections on five widths, OTP cancellation/network recovery, failed safeguard rollback, moving backgrounds/reduced motion/hidden pause, empty archive; no JS errors')
  await b.close()
asyncio.run(main())
