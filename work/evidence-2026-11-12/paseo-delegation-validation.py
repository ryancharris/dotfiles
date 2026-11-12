"""Task-owned Paseo delegation probe; never saves credentials or unrelated config values."""
import hashlib,json,os,subprocess,sys,time,shutil
from pathlib import Path
TASK=Path('/private/tmp/ade-paseo-matrix-20261112')
DAEMON_HOME=TASK/'home'
OUT=Path(__file__).resolve().parent
STATE=TASK/'probe-state.json'
TARGETS=[Path('/Users/ryan')/p for p in ['.claude/settings.json','.claude.json','.codex/config.toml','.codex/hooks.json','.cursor/mcp.json','.gemini/settings.json','.zshrc','.zprofile','.bashrc','.config/fish/config.fish','.config/opencode/opencode.json','.config/opencode/opencode.jsonc']]

def fingerprint():
 return {str(i):hashlib.sha256(i.read_bytes()).hexdigest() if i.is_file() else None for i in TARGETS}
def cli(*args,timeout=50):
 r=subprocess.run(['paseo',*args,'--home',str(DAEMON_HOME),'--json'],capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError('Paseo command failed: '+args[0]+' exit '+str(r.returncode))
 try:return json.loads(r.stdout)
 except json.JSONDecodeError:
  if args[0]=='logs':return r.stdout
  raise
if sys.argv[1]=='setup':
 TASK.mkdir(exist_ok=False);DAEMON_HOME.mkdir();(TASK/'fixture').mkdir()
 (DAEMON_HOME/'config.json').write_text(json.dumps({'daemon':{'listen':'127.0.0.1:6823','mcp':{'enabled':True,'injectIntoAgents':True}}}))
 print(json.dumps({'daemon_started':cli('daemon','start').get('action')=='started'}))
elif sys.argv[1]=='start':
 before=fingerprint()
 prompt=('This is an authorized local app delegation validation. Do not read or modify files or execute shell commands. Use only Paseo MCP tools. Discover profiles/providers if needed. Create exactly one child agent with provider codex/gpt-6.1-sol in this same workspace, title ADE delegation child, and initialPrompt: Reply exactly PASEO_DELEGATION_CHILD_OK. Do not use tools, read files, write files, or create any further agents. Set notifyOnFinish true. Collect that actual child response using its activity/status or notification. Do not infer success from the prompt. Your final answer must contain the actual childAgentId, observed child status, and exact observed assistant response. No other work.')
 run=cli('run','--provider','codex/gpt-6.1-sol','--thinking','low','--mode','auto-review','--cwd',str(TASK/'fixture'),'--no-wait','--title','ADE delegation validation',prompt)
 STATE.write_text(json.dumps({'before':before,'run':run}))
 print(json.dumps({'started':True,'receipt':run}))
elif sys.argv[1]=='collect':
 state=json.loads(STATE.read_text());rid=state['run'].get('agentId')
 if not rid:raise RuntimeError('missing parent id')
 info=cli('inspect',rid)
 logs=cli('logs',rid,'--tail','100')
 # These test-only responses contain no credentials; keep locally for structural analysis before sanitizing output.
 (TASK/'parent-inspect.json').write_text(json.dumps(info,indent=2))
 (TASK/'parent-logs.json').write_text(json.dumps(logs,indent=2))
 print(json.dumps({'inspect_keys':list(info),'logs_type':type(logs).__name__,'logs_keys':list(logs) if isinstance(logs,dict) else [],'parentId':rid}))
elif sys.argv[1]=='verify':
 state=json.loads(STATE.read_text());rid=state['run']['agentId'];info=cli('inspect',rid);logs=cli('logs',rid,'--tail','100')
 import re
 matches=re.findall(r'\[Read agent activity\] \{"agentId":"([^"]+)"',logs)
 if len(set(matches))!=1:raise RuntimeError('one independently observed child id required')
 cid=matches[0];child=cli('inspect',cid);childlogs=cli('logs',cid,'--tail','100')
 result={'app_version':'0.15.4','route':'Isolated installed Paseo daemon, Codex parent and child via injected MCP','parent':{k:info.get(k) for k in ['Id','Provider','Model','Status','ParentAgentId']},'child':{k:child.get(k) for k in ['Id','Provider','Model','Status','ParentAgentId']},'parent_create_tool_calls':sum(l.startswith('[Create agent]') for l in logs.splitlines()),'parent_read_child_activity':cid in matches,'parent_received_finish_notification':('[Agent finished]' in logs and '<agent-response>\nPASEO_DELEGATION_CHILD_OK' in logs),'child_independent_assistant_marker_lines':sum(l.strip()=='PASEO_DELEGATION_CHILD_OK' for l in childlogs.splitlines()),'child_lineage_matches':child.get('ParentAgentId')==rid,'parent_observed_response':'PASEO_DELEGATION_CHILD_OK' if 'Exact assistant response observed in activity: `PASEO_DELEGATION_CHILD_OK`' in logs else None,'child_tool_calls_observed':sum(l.startswith(('[Shell]','[Create agent]','[Read agent activity]')) for l in childlogs.splitlines())}
 result['passed']=result['parent_create_tool_calls']==1 and result['parent_read_child_activity'] and result['parent_received_finish_notification'] and result['child_independent_assistant_marker_lines']>0 and result['child_lineage_matches'] and result['parent_observed_response'] is not None
 (OUT/'paseo-delegation-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
elif sys.argv[1]=='cleanup':
 state=json.loads(STATE.read_text());rid=state['run']['agentId'];info=cli('inspect',rid)
 ws=state['run'].get('workspaceId')
 if not ws:
  matches=[x for x in json.loads((DAEMON_HOME/'projects/workspaces.json').read_text()) if x['cwd']==str(TASK/'fixture')]
  if len(matches)!=1:raise RuntimeError('owned workspace not uniquely identified')
  ws=matches[0]['workspaceId']
 if ws:arch=cli('workspace','archive',ws)
 else:arch={'not_requested':True}
 stopped=cli('daemon','stop')
 after=fingerprint();same={str(i.relative_to('/Users/ryan')):state['before'][str(i)]==after[str(i)] for i in TARGETS}
 result={'config_comparison':same,'all_monitored_configs_unchanged':all(same.values()),'workspace_archived':arch.get('status')=='archived','daemon_stopped':stopped.get('action')=='stopped'}
 if stopped.get('action')=='stopped':
  shutil.rmtree(TASK);result['temporary_profile_removed']=True
 (OUT/'paseo-delegation-cleanup.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
