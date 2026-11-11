"""Validate both local comparison views in isolated headless Chrome; refresh social export."""
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
 url=targets[0]['webSocketDebuggerUrl']; host='127.0.0.1'; path='/'+'/'.join(url.split('/')[3:]); sock=socket.create_connection((host,int(port))); key=base64.b64encode(os.urandom(16)).decode(); sock.sendall(f'GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode()); resp=sock.recv(4096); assert b'HTTP/1.1 101' in resp, resp
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
 records=[]
 for file in ['ade-comparison-share.html','ade-comparison-detailed.html']:
  for width in [390,768,1400]:
   call('Emulation.setDeviceMetricsOverride',{'width':width,'height':900,'deviceScaleFactor':1,'mobile':width==390}); call('Page.navigate',{'url':(base/file).as_uri()})
   for _ in range(50):
    if ev('document.readyState')=='complete':break
    time.sleep(.1)
   result=ev('''(()=>{let d=document.querySelector('details'); let b=d.open; d.querySelector('summary').click(); let a=d.open; d.querySelector('summary').click(); return {title:document.title,viewport:innerWidth,bodyWidth:document.documentElement.scrollWidth,detailsBefore:b,detailsAfter:a,detailsReset:d.open,tableCount:document.querySelectorAll('table').length,tableOverflow:[...document.querySelectorAll('.table-wrap')].map(x=>[x.clientWidth,x.scrollWidth]),topOverflow:[...document.querySelectorAll('body *')].filter(x=>{let r=x.getBoundingClientRect();return r.right>innerWidth+1&&!x.closest('.table-wrap')}).map(x=>x.tagName+'.'+x.className).slice(0,8)} })()''')
   assert result['bodyWidth'] <= width, result
   assert result['detailsBefore'] is False and result['detailsAfter'] is True and result['detailsReset'] is False, result
   assert result['tableCount'] == 2 and not result['topOverflow'], result
   result['apps']=ev("[...document.querySelectorAll('tbody')].map(t=>[...t.rows].map(r=>r.dataset.app))")
   expected=['Orca','Paseo','cmux','Herdr','Sheprd','T3 Code']
   assert result['apps']==[expected,expected],result
   if file.endswith('detailed.html'):
    result['selector']=ev('''(()=>{let l=document.querySelector('#left'),r=document.querySelector('#right'),rows=[...document.querySelectorAll('tr[data-app]')],checks=[];for(let a of [...l.options].map(o=>o.value)){for(let b of [...r.options].map(o=>o.value)){l.value=a;l.dispatchEvent(new Event('change',{bubbles:true}));r.value=b;r.dispatchEvent(new Event('change',{bubbles:true}));let shown=rows.filter(e=>!e.hidden).map(e=>e.dataset.app);checks.push(shown.length===(a===b?2:4)&&shown.every(x=>x===a||x===b));}}document.querySelector('#all').click();return {options:[...l.options].map(o=>o.value),rightOptions:[...r.options].map(o=>o.value),pairs:checks.length,allPairsPassed:checks.every(Boolean),all:rows.filter(e=>!e.hidden).length}})()''')
    assert sorted(result['selector']['options'])==sorted(expected),result
    assert sorted(result['selector']['rightOptions'])==sorted(expected),result
    assert result['selector']['pairs']==36 and result['selector']['allPairsPassed'] and result['selector']['all']==12,result
   result['fieldGrades']=ev("[...document.querySelectorAll('tbody tr')].map(r=>({app:r.dataset.app,grades:[...r.querySelectorAll('td:not(:first-child)')].map(c=>({count:c.querySelectorAll('[data-grade]').length,grade:c.querySelector('[data-grade]')?.dataset.grade}))}))")
   seen={app:0 for app in expected}
   for row in result['fieldGrades']:
    offset=seen[row['app']]*4;seen[row['app']]+=1
    assert all(c['count']==1 for c in row['grades']),result
    assert [c['grade'] for c in row['grades']]==list(manifest['apps'][row['app']].values())[offset:offset+4],result
   result['gradeLegend']=ev("[...document.querySelectorAll('.grade-key [data-grade]')].map(g=>g.dataset.grade)")
   assert result['gradeLegend']==list(manifest['rubric']),result
   records.append({'file':file,**result})
   print(file,width,'PASS: 48 field grades; disclosure; layout; '+('36 selector pairs' if file.endswith('detailed.html') else '6 apps in both tables'))
   if width in (390,1400):
    snap=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'fromSurface':True});(Path(tempfile.gettempdir())/(file.replace('.html','')+'-'+str(width)+'.png')).write_bytes(base64.b64decode(snap['data']))
   if file=='ade-comparison-share.html' and width==1400:
    (base/'ade-comparison-social.png').write_bytes(base64.b64decode(snap['data']))
 source_rows=[]
 for filename in ['ade-comparison-share.html','ade-comparison-detailed.html']:
  import re
  html=(base/filename).read_text()
  source_rows.append(re.findall(r'<tr data-app="[^"]+">.*?</tr>',html,re.S))
  assert not re.search(r'Four ways|04 candidates|Show all four|sk-or-v1-[a-fA-F0-9]{64}',html)
 assert source_rows[0]==source_rows[1]
 (base/'comparison-validation.json').write_text(json.dumps({'passed':True,'apps':6,'field_grades_per_view':48,'table_content_parity':True,'records':records},indent=2)+'\n')
finally:
 p.terminate();p.wait(timeout=5);profile.cleanup()
