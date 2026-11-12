"""Validate both comparison views and the social card against comparison-grades.json in isolated headless Chrome; refresh the social export."""
import base64,json,os,socket,struct,subprocess,tempfile,time,urllib.request
from pathlib import Path
chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
profile=tempfile.TemporaryDirectory(prefix='ade-cdp-')
p=subprocess.Popen([chrome,'--headless','--disable-gpu','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+profile.name,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 portfile=Path(profile.name)/'DevToolsActivePort'
 for _ in range(100):
  if portfile.exists(): break
  time.sleep(.1)
 port=portfile.read_text().splitlines()[0]
 targets=json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list'))
 url=targets[0]['webSocketDebuggerUrl']; host='127.0.0.1'; path='/'+'/'.join(url.split('/')[3:]); sock=socket.create_connection((host,int(port)),timeout=20); key=base64.b64encode(os.urandom(16)).decode(); sock.sendall(f'GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode()); resp=sock.recv(4096); assert b'HTTP/1.1 101' in resp, resp
 def recv(n):
  b=b''
  while len(b)<n:
   s=sock.recv(n-len(b))
   if not s: raise RuntimeError('closed')
   b+=s
  return b
 def read():
  h=recv(2); length=h[1]&127
  if length==126:length=struct.unpack('!H',recv(2))[0]
  elif length==127:length=struct.unpack('!Q',recv(8))[0]
  return json.loads(recv(length))
 seq=0
 def call(method,params={}):
  global seq
  seq+=1; payload=json.dumps({'id':seq,'method':method,'params':params}).encode(); n=len(payload); hdr=bytes([0x81,0x80|n]) if n<126 else bytes([0x81,0x80|126])+struct.pack('!H',n) if n<65536 else bytes([0x81,0x80|127])+struct.pack('!Q',n); mask=os.urandom(4); sock.sendall(hdr+mask+bytes(c^mask[i%4] for i,c in enumerate(payload)))
  while 1:
   result=read()
   if result.get('id')==seq:
    if 'error' in result: raise Exception(result)
    return result.get('result',{})
 def ev(expression):
  x=call('Runtime.evaluate',{'expression':expression,'returnByValue':True});
  if 'exceptionDetails' in x: raise Exception(x['exceptionDetails'])
  return x['result'].get('value')
 call('Page.enable');call('Runtime.enable')
 base=Path(__file__).resolve().parent
 manifest=json.loads((base/'comparison-grades.json').read_text())
 apps=list(manifest['apps']); fields=manifest['fields']; n=len(apps)
 tiers=['entry','hard','extra']; tier_fields={t:[k for k,f in fields.items() if f['tier']==t] for t in tiers}
 assert all(set(a['grades'])==set(fields) for a in manifest['apps'].values()), 'every app must grade every field'
 assert all(g['grade'] in manifest['rubric'] for a in manifest['apps'].values() for g in a['grades'].values())
 assert all(a.get('tested_version') for a in manifest['apps'].values()), 'tested_version missing'
 assert manifest['apps']['T3 Code']['tested_version']=='0.1.5' and manifest['apps']['T3 Code']['current_version']=='0.1.9'
 rk=manifest['ranking']; passed=[a for a,v in manifest['apps'].items() if v['status']=='passed']
 for pick in ['personal','general']:
  assert len(rk[pick])==3 and len(set(rk[pick]))==3, 'exactly three recommendations are required'
  assert set(rk[pick])<=set(apps), 'recommendations must name tested apps'
  for name in rk[pick]:
   candidate=manifest['apps'][name]
   assert candidate['status']!='failed', 'failed app cannot be recommended'
   gates=[f for f,d in fields.items() if d['tier'] in ('entry','hard') and d['applies'] in ('both',pick)]
   assert all(candidate['grades'][f]['grade']!='gap' for f in gates), 'recommendation has an observed hard gap'
   assert rk['reasons'].get(name) and rk['card_notes'].get(name), 'recommendation needs visible reasons'
 assert rk['identical']==(rk['personal']==rk['general'])
 assert not {'Herdr','cmux'}&set(apps+rk['personal']+rk['general']), 'Herdr/cmux must not be candidates'
 for a,v in manifest['apps'].items():
  gates=[f for f,desc in fields.items() if desc['tier'] in ('entry','hard') and desc['applies'] in ('both','personal','general')]
  if v['status']=='passed':
   assert all(v['grades'][f]['grade']=='proven' for f in gates), (a, 'passing app has an incomplete hard or entry gate')
  elif v['status']=='failed':
   assert v['failed_on'] and all(f in gates and v['grades'][f]['grade']=='gap' for f in v['failed_on']), a
  else:
   assert v['status']=='unqualified' and v['unverified_on'] and all(f in gates and v['grades'][f]['grade'] in ('partial','supported','unknown') for f in v['unverified_on']), a
 for name in manifest.get('runtime_validation',{}).get('authenticated_api_pending',[]):
  assert manifest['apps'][name]['grades']['entry_keys']['grade']!='proven' and manifest['apps'][name]['status']!='passed', 'authenticated API-key response still unverified'
 for name,app in manifest['apps'].items():
  license=app.get('license',{})
  assert all(license.get(k) for k in ['id','label','short_label','source_url','scope_note']), (name,'specific license/source missing')
  assert license['source_url'].startswith('https://'), (name,'license needs a primary source link')
 n_cells=n*len(fields)
 records=[]
 for file in ['ade-comparison-share.html','ade-comparison-detailed.html']:
  for width in [390,768,1400]:
   call('Emulation.setDeviceMetricsOverride',{'width':width,'height':900,'deviceScaleFactor':1,'mobile':width==390}); call('Page.navigate',{'url':(base/file).as_uri()})
   for _ in range(50):
    if ev('document.readyState')=='complete':break
    time.sleep(.1)
   result=ev('''(()=>{let d=document.querySelector('details'); let b=d.open; d.querySelector('summary').click(); let a=d.open; d.querySelector('summary').click(); return {title:document.title,viewport:innerWidth,bodyWidth:document.documentElement.scrollWidth,detailsBefore:b,detailsAfter:a,detailsReset:d.open,tableCount:document.querySelectorAll('table').length,topOverflow:[...document.querySelectorAll('body *')].filter(x=>{let r=x.getBoundingClientRect();return r.right>innerWidth+1&&!x.closest('.table-wrap')}).map(x=>x.tagName+'.'+x.className).slice(0,8),picks:Object.fromEntries([...document.querySelectorAll('[data-pick]')].map(p=>[p.dataset.pick,[...p.querySelectorAll('.rank strong')].map(s=>s.textContent)]))} })()''')
   assert result['bodyWidth'] <= width, result
   assert result['detailsBefore'] is False and result['detailsAfter'] is True and result['detailsReset'] is False, result
   assert result['tableCount'] == 3 and not result['topOverflow'], result
   for pick in ['personal','general']:
    assert result['picks'][pick]==[x.upper() for x in rk[pick]], result['picks']
   result['recommendationLabels']=ev("[...document.querySelectorAll('.rank[data-app]')].map(r=>({app:r.dataset.app,state:r.dataset.qualification,text:r.textContent}))")
   for row in result['recommendationLabels']:
    expected='qualified' if manifest['apps'][row['app']]['status']=='passed' else 'provisional'
    assert row['state']==expected and expected.capitalize() in row['text'] and rk['reasons'][row['app']] in row['text'], row
   result['apps']=ev("[...document.querySelectorAll('tbody')].map(t=>[...t.rows].map(r=>r.dataset.app))")
   assert result['apps']==[apps]*3,result
   if file.endswith('detailed.html'):
    result['selector']=ev('''(()=>{let l=document.querySelector('#left'),r=document.querySelector('#right'),rows=[...document.querySelectorAll('tr[data-app]')],checks=[];for(let a of [...l.options].map(o=>o.value)){for(let b of [...r.options].map(o=>o.value)){l.value=a;l.dispatchEvent(new Event('change',{bubbles:true}));r.value=b;r.dispatchEvent(new Event('change',{bubbles:true}));let shown=rows.filter(e=>!e.hidden).map(e=>e.dataset.app);checks.push(shown.length===(a===b?3:6)&&shown.every(x=>x===a||x===b));}}document.querySelector('#all').click();return {options:[...l.options].map(o=>o.value),rightOptions:[...r.options].map(o=>o.value),pairs:checks.length,allPairsPassed:checks.every(Boolean),all:rows.filter(e=>!e.hidden).length}})()''')
    assert sorted(result['selector']['options'])==sorted(apps) and sorted(result['selector']['rightOptions'])==sorted(apps),result
    assert result['selector']['pairs']==n*n and result['selector']['allPairsPassed'] and result['selector']['all']==3*n,result
   result['fieldGrades']=ev("[...document.querySelectorAll('table')].map(t=>[...t.tBodies[0].rows].map(r=>({app:r.dataset.app,grades:[...r.querySelectorAll('td:not(:first-child)')].map(c=>({count:c.querySelectorAll('[data-grade]').length,grade:c.querySelector('[data-grade]')?.dataset.grade}))})))")
   for tier,table in zip(tiers,result['fieldGrades']):
    for row in table:
     assert all(c['count']==1 for c in row['grades']),row
     assert [c['grade'] for c in row['grades']]==[manifest['apps'][row['app']]['grades'][f]['grade'] for f in tier_fields[tier]],(tier,row)
   result['licenses']=ev("[...document.querySelectorAll('.license-label')].map(l=>({app:l.dataset.licenseApp,id:l.dataset.licenseId,label:l.textContent,url:l.getAttribute('href')}))")
   assert len(result['licenses'])==3*n, 'each app needs a license in every table'
   for lic in result['licenses']:
    expected=manifest['apps'][lic['app']]['license']
    assert lic['id']==expected['id'] and lic['label']==expected['label'] and lic['url']==expected['source_url'], lic
   result['gradeLegend']=ev("[...document.querySelectorAll('.grade-key [data-grade]')].map(g=>g.dataset.grade)")
   assert result['gradeLegend']==list(manifest['rubric']),result
   del result['fieldGrades']
   records.append({'file':file,**result})
   print(file,width,f'PASS: {n_cells} field grades; 3 tables; both pick lists; disclosure; layout'+(f'; {n*n} selector pairs' if file.endswith('detailed.html') else ''))
   if width in (390,1400):
    snap=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'fromSurface':True});(Path(tempfile.gettempdir())/(file.replace('.html','')+'-'+str(width)+'.png')).write_bytes(base64.b64decode(snap['data']))
 call('Emulation.setDeviceMetricsOverride',{'width':1080,'height':1350,'deviceScaleFactor':2,'mobile':False}); call('Page.navigate',{'url':(base/'ade-comparison-card.html').as_uri()})
 for _ in range(50):
  if ev("document.readyState==='complete'&&document.querySelectorAll('.grid .chip').length>0"): break
  time.sleep(.1)
 call('Runtime.evaluate',{'expression':'document.fonts.ready.then(()=>1)','awaitPromise':True})
 card=ev('''(()=>({w:document.documentElement.scrollWidth,h:document.documentElement.scrollHeight,foot:document.querySelector('.foot').getBoundingClientRect().bottom,
  overflow:[...document.querySelectorAll('.card *')].filter(x=>{let r=x.getBoundingClientRect();return r.right>1080||r.bottom>1350}).map(x=>x.tagName+'.'+x.className),
  minFont:Math.min(...[...document.querySelectorAll('.card *')].filter(x=>[...x.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())).map(x=>parseFloat(getComputedStyle(x).fontSize))),
  h1:document.querySelector('h1').textContent,ranks:[...document.querySelectorAll('.verdict b')].map(b=>b.textContent),vhead:document.querySelector('.vhead').textContent,
  notes:[...document.querySelectorAll('.pick-note')].map(n=>({app:n.dataset.app,state:n.dataset.qualification,text:n.textContent})),numbers:[...document.querySelectorAll('.verdict i')].map(n=>n.textContent),
  licenses:[...document.querySelectorAll('.grid .app')].map(a=>({app:a.dataset.app,id:a.querySelector('.app-license').dataset.licenseId,label:a.querySelector('.app-license').textContent})),
  labelOverflow:[...document.querySelectorAll('.app-name,.app-license')].filter(e=>{const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return r.right>p.right+.5||r.top<p.top||r.bottom>p.bottom+.5}).map(e=>e.textContent),
  rows:[...document.querySelectorAll('.grid .app')].map(a=>a.dataset.app),cells:[...document.querySelectorAll('.grid .chip')].map(c=>[c.dataset.app,c.dataset.field,c.dataset.grade])}))()''')
 assert card['w']==1080 and card['h']==1350 and card['foot']<=1350 and not card['overflow'], card
 assert card['minFont']>=24, ('card text below 24px', card['minFont'])
 assert card['rows']==apps, card['rows']
 assert len(card['licenses'])==n and not card['labelOverflow'], ('license/name clipping',card['labelOverflow'])
 for lic in card['licenses']:
  expected=manifest['apps'][lic['app']]['license']
  assert lic['id']==expected['id'] and lic['label']==expected['short_label'], lic
 card_fields=sorted({c[1] for c in card['cells']})
 assert 1<=len(card_fields)<=8 and len(card['cells'])==n*len(card_fields), 'card grid shape'
 assert all(manifest['apps'][a]['grades'][f]['grade']==g for a,f,g in card['cells']), 'card grades differ from manifest'
 assert card['ranks']==rk['personal'] and (not rk['identical'] or 'fresh setup' in card['vhead'].lower()), card
 assert card['numbers']==['1','2','3'] and len(card['notes'])==3, 'numbered top three missing'
 for note in card['notes']:
  expected='qualified' if manifest['apps'][note['app']]['status']=='passed' else 'provisional'
  assert note['state']==expected and note['text']==rk['card_notes'][note['app']], note
  if expected=='provisional': assert 'Provisional' in note['text'], 'incomplete recommendation needs a visible provisional label'
 words={0:'none',1:'one',2:'two',3:'three',4:'four',5:'five',6:'six',7:'seven',8:'eight',9:'nine',10:'ten'}
 assert card['h1'].lower().startswith(words[n]) and 'my top three' in card['h1'].lower() and 'top 3' in card['vhead'].lower(), card['h1']
 snap=call('Page.captureScreenshot',{'format':'png','clip':{'x':0,'y':0,'width':1080,'height':1350,'scale':1}})
 (base/'ade-comparison-social.png').write_bytes(base64.b64decode(snap['data']))
 print(f'ade-comparison-card.html 1080x1350 PASS: {len(card["cells"])} grades match manifest; text >= 24px; no overflow; exported 2160x2700')
 import re
 stale=[r'Next to validate',r'Incomplete hard gates stay open',r'Only fully verified candidates fill',r'slots stay open',r'six ways',r'show all six',r'06 candidates',r'four ways',r'04 candidates',r'show all four',r'sk-or-v1-[a-fA-F0-9]{64}']
 if n!=6: stale.append(r'six ades')
 source_rows=[]
 for filename in ['ade-comparison-share.html','ade-comparison-detailed.html','ade-comparison-card.html','README-ade-comparison.md']:
  text=(base/filename).read_text()
  for pat in stale: assert not re.search(pat,text,re.I),(filename,pat)
  assert not re.search(r'data-app="(Herdr|cmux)"',text),(filename,'Herdr/cmux as a candidate')
  for block in re.findall(r'class="(?:verdict|picks)".*?</section>',text,re.S):
   assert 'Herdr' not in re.sub(r'Herdr 2','',block) and 'cmux' not in block,(filename,'Herdr/cmux ranked')
  if filename.endswith('.html') and 'card' not in filename: source_rows.append(re.findall(r'<tr data-app="[^"]+".*?</tr>',text,re.S))
 assert source_rows[0]==source_rows[1] and len(source_rows[0])==3*n
 (base/'comparison-validation.json').write_text(json.dumps({'passed':True,'apps':n,'passed_apps':passed,'card':{k:v for k,v in card.items() if k!='cells'},'hard_gate_invariant':True,'runtime_qualification_complete':not manifest.get('runtime_validation',{}).get('authenticated_api_pending',[]),'runtime_api_pending':manifest.get('runtime_validation',{}).get('authenticated_api_pending',[]),'ranked_recommendations':rk['personal'],'provisional_labels_verified':True,'specific_licenses_verified':True,'field_grades_per_view':n_cells,'card_fields':card_fields,'table_content_parity':True,'records':records},indent=2,ensure_ascii=False)+'\n')
finally:
 p.terminate();p.wait(timeout=5);profile.cleanup()
