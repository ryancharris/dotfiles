"""Sheprd terminal and native-chat/core compatibility probe on the test host.

Reuses an existing app and core; never installs/updates software. This starts a
visible isolated app, so coordinate foreground ownership first. The operator
may need to inspect/allow the task-owned core run/wait/read permission prompts.
Only own temporary state is deleted; normal agent CLI transcripts are retained.
SHA-256 values stay in memory; only comparison booleans are published.
"""
from pathlib import Path
import subprocess,os,time,json,tempfile,hashlib,shlex,re,sys,shutil
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--bundle',type=Path,default=Path('/private/tmp/sheprd-config-test-release/Sheprd.app'))
parser.add_argument('--core',type=Path,default=Path.home()/'.local/bin/herdr-core')
parser.add_argument('--startup-only',action='store_true',help='Verify startup/input without any model requests')
args=parser.parse_args()
bin=args.bundle/'Contents/MacOS'
core_bin=args.core
repo=Path.cwd();root=Path(tempfile.mkdtemp(prefix='sv-',dir='/private/tmp'));(root/'runtime').mkdir(mode=0o700)
env={**os.environ,'XDG_CONFIG_HOME':str(root/'config'),'XDG_STATE_HOME':str(root/'state'),'XDG_DATA_HOME':str(root/'data'),'XDG_CACHE_HOME':str(root/'cache'),'XDG_RUNTIME_DIR':str(root/'runtime'),'HERDR_HOME':str(root/'herdr'),'HC_SOCKET':str(root/'core.sock'),'HC_SESSION':'ade-startup-validation'}
BASE_CHECK_ZSH='# Source in the app-created test shell. Only boolean/count output.\nunset HISTFILE\nunsetopt SHARE_HISTORY\npaseo_zsh_bool() { if "$@"; then print true; else print false; fi }\nprint PASEO_ZSH_CHECK_BEGIN\nprint "interactive=$([[ -o interactive ]] && print true || print false)"\nprint "login=$([[ -o login ]] && print true || print false)"\nprint "real_home=$([[ $HOME == __HOME__ ]] && print true || print false)"\nprint "default_zdotdir=$([[ ${ZDOTDIR:-$HOME} == $HOME ]] && print true || print false)"\nprint "gs_alias=$(( $+aliases[gs] ))"\nprint "gro_function=$(( $+functions[gro] ))"\nfor paseo_zsh_tool in brew gh starship direnv fzf zoxide fd; do\n  print "tool_${paseo_zsh_tool}=$(( $+commands[$paseo_zsh_tool] ))"\ndone\nfor paseo_zsh_var in ASDF_DATA_DIR GOPATH GOBIN GIT_PROJECTS_WORKDIR FZF_DEFAULT_COMMAND FZF_CTRL_T_COMMAND FZF_DEFAULT_OPTS; do\n print "export_${paseo_zsh_var}=$([[ ${(tP)paseo_zsh_var} == *export* ]] && print true || print false)"\ndone\npython3 __FILE_CHECK__\npaseo_zsh_local_count=0\npaseo_zsh_local_defined=0\nwhile IFS=\'|\' read -r paseo_zsh_kind paseo_zsh_name; do\n (( paseo_zsh_local_count++ ))\n case $paseo_zsh_kind in\n  parameter) (( $+parameters[$paseo_zsh_name] )) && (( paseo_zsh_local_defined++ ));;\n  alias) (( $+aliases[$paseo_zsh_name] )) && (( paseo_zsh_local_defined++ ));;\n  function) (( $+functions[$paseo_zsh_name] )) && (( paseo_zsh_local_defined++ ));;\n esac\ndone < <(python3 __FILE_CHECK__ --names)\nprint "private_declarations_detected=$paseo_zsh_local_count"\nprint "private_declarations_defined=$paseo_zsh_local_defined"\nprint PASEO_ZSH_CHECK_END\nunfunction paseo_zsh_bool\nunset paseo_zsh_tool paseo_zsh_var paseo_zsh_kind paseo_zsh_name paseo_zsh_local_count paseo_zsh_local_defined\n'
CHECK_FILES_PY='from pathlib import Path\nimport re,sys\nhome=Path.home()\nprivate=home/\'.zshrc.local\'\nif \'--names\' in sys.argv:\n    if private.is_file():\n        text=private.read_text()\n        entries=set()\n        for line in text.splitlines():\n            for kind,pattern in [(\'parameter\',r\'^\\s*(?:export\\s+)?([A-Za-z_][A-Za-z0-9_]*)=\'),(\'alias\',r\'^\\s*alias\\s+([A-Za-z_][A-Za-z0-9_]*)=\'),(\'function\',r\'^\\s*([A-Za-z_][A-Za-z0-9_]*)\\s*\\(\\)\\s*\\{\')]:\n                match=re.match(pattern,line)\n                if match:entries.add((kind,match.group(1)))\n        for kind,name in sorted(entries): print(kind+\'|\'+name)\nelse:\n    expected=(home/\'dotfiles/zsh\')\n    for name in (\'.zshrc\',\'.zprofile\'):\n        print(name.lstrip(\'.\')+\'_links_dotfiles=\'+str((home/name).resolve()==expected/name).lower())\n    print(\'private_local_rc_present=\'+str(private.is_file()).lower())\n    configured=\'source "$HOME/.zshrc.local"\' in (home/\'.zshrc\').read_text()\n    print(\'private_local_rc_source_configured=\'+str(configured).lower())\n'
file_check=root/'check-files.py';file_check.write_text(CHECK_FILES_PY)
shell_check=root/'check.zsh';shell_check.write_text(BASE_CHECK_ZSH.replace('__FILE_CHECK__',shlex.quote(str(file_check))).replace('__HOME__',str(Path.home())))
labels=['.claude/settings.json','.claude.json','.codex/config.toml','.codex/hooks.json','.cursor/mcp.json','.config/opencode/opencode.json','.config/opencode/opencode.jsonc','.gemini/settings.json','.zshenv','.zprofile','.zshrc','.zlogin','.zshrc.local']
def hashes():
 out={}
 for label in labels:
  p=Path.home()/label
  try:out[label]=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
  except OSError:out[label]='unreadable'
 return out
def cmd(name,*args,timeout=15):return subprocess.run([str(core_bin if name=='herdr-core' else bin/name),*args],env=env,capture_output=True,text=True,timeout=timeout)
def hc(*args,timeout=15):
 r=cmd('herdr-core',*args,timeout=timeout)
 if r.returncode:raise RuntimeError('core command failed: '+str(args[:2])+' exit '+str(r.returncode))
 return r.stdout
def read(t):return hc('read',t)
def checks(t):
 line=" unset HISTFILE; unsetopt SHARE_HISTORY; sv_original_prompt_present=$([[ -n $PROMPT ]] && print true || print false); PROMPT='> '; RPROMPT=''; source "+shlex.quote(str(shell_check))+"; print rcs=$([[ -o rcs ]] && print true || print false); print globalrcs=$([[ -o globalrcs ]] && print true || print false); print shell_executable_matches_configured=$([[ $(ps -p $$ -o comm=) == *zsh* && $SHELL == /bin/zsh ]] && print true || print false); print prompt_present=$sv_original_prompt_present; [[ $(bindkey '^A') == *beginning-of-line* ]] && print binding_ctrl_a=true || print binding_ctrl_a=false; [[ $(bindkey '^K') == *kill-line* ]] && print binding_ctrl_k=true || print binding_ctrl_k=false; print SV_CHECKS_DONE"
 hc('send',t,line)
 for _ in range(50):
  raw=read(t)
  if any(x.strip()=='SV_CHECKS_DONE' for x in raw.splitlines()):break
  time.sleep(.1)
 result={}
 for line in raw.splitlines():
  line=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',line).strip()
  if re.fullmatch(r'[A-Za-z0-9_]+=(true|false|\d+)',line):k,v=line.split('=',1);result[k]=v
 return result,raw
before=hashes();p=None;core=False
result={'tested_release':'20261109.1','core':subprocess.run([str(core_bin),'--version'],capture_output=True,text=True,check=True).stdout.strip(),'route':'Pre-started existing installed core in isolated supported socket; pinned Sheprd app connects and creates/shows new terminal','result':'partial','config':{'file':'$XDG_CONFIG_HOME/herdr-core/config.toml','shell':['/bin/zsh','-l','-o','sourcetrace']},'external_hashes_before':before}
try:
 cfg=root/'config/herdr-core/config.toml';cfg.parent.mkdir(parents=True);cfg.write_text('shell = ["/bin/zsh", "-l", "-o", "sourcetrace"]\nnotes = false\n')
 r=cmd('herdr-core','server','start','--json');result['isolated_core_start_exit']=r.returncode
 if r.returncode:raise RuntimeError('isolated core start failed')
 core=True
 p=subprocess.Popen([str(bin/'sheprd')],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for _ in range(80):
  r=cmd('sheprd','status','--json',timeout=3)
  if r.returncode==0 and json.loads(hc('ls','--all','--json')).get('terminals'):break
  time.sleep(.1)
 result['app_control_reachable']=r.returncode==0
 if r.returncode:raise RuntimeError('app unavailable')
 result['window_count']=len(json.loads(r.stdout).get('windows',[]))
 initial=json.loads(hc('ls','--all','--json'))['terminals'];initial_addresses={t['address'] for t in initial};result['app_created_terminal_count']=len(initial);result['terminal_addresses_before_action']=sorted(initial_addresses)
 r=cmd('sheprd','run','new_core_terminal','--json');result['new_gui_terminal_action_exit']=r.returncode
 time.sleep(.5)
 terminals=json.loads(hc('ls','--all','--json'))['terminals'];result['terminal_count_after_action']=len(terminals)
 new_addresses={t['address'] for t in terminals}-initial_addresses
 result['new_terminal_addresses_after_action']=sorted(new_addresses)
 result['terminal_owned_by_test']=r.returncode==0 and len(new_addresses)==1 and len(terminals)==len(initial)+1
 if not result['terminal_owned_by_test']:raise RuntimeError('App action did not create exactly one new terminal')
 terminal=next(iter(new_addresses));result['tested_terminal_address']=terminal
 raw_start=read(terminal)
 result['startup_trace']={k:any((str(Path.home()/v) in line) for line in raw_start.splitlines()) for k,v in [('zprofile','.zprofile'),('zshrc','.zshrc'),('zshrc_local','.zshrc.local')]}
 shell,raw=checks(terminal);result['shell_checks']=shell
 # Actual line-editing key events in the SAME app-owned terminal.
 hc('keys',terminal,'s','v','d','i','s','c','a','r','d')
 marker_before='svdiscard' in read(terminal)
 hc('keys',terminal,'ctrl+a','ctrl+k')
 hc('send',terminal,' print SV_INPUT_OK')
 raw=read(terminal)
 result['input']={'discard_marker_observed':marker_before,'configured_ctrl_a':shell.get('binding_ctrl_a')=='true','configured_ctrl_k':shell.get('binding_ctrl_k')=='true','marker_erased':'svdiscard' not in raw,'expected_output_observed':any(x.strip()=='SV_INPUT_OK' for x in raw.splitlines()),'route':'first-party core key events into the same app-created GUI terminal; no OS-global input'}
 r=cmd('sheprd','tab','list','--json');result['app_tab_list_exit']=r.returncode
 if r.returncode==0:
  obj=json.loads(r.stdout);result['app_tab_count']=len(obj.get('tabs',[])) if isinstance(obj,dict) else len(obj)
 result['external_hashes_before_chat']=hashes()
 result['app_startup_external_files_unchanged']=before==result['external_hashes_before_chat']
 if args.startup_only:
  hc('send',terminal,'claude')
  raw_cli=''
  for _ in range(100):
   raw_cli=read(terminal)
   if 'Claude Code' in raw_cli or 'Do you trust' in raw_cli:break
   time.sleep(.1)
  process_result=cmd('sheprd','processes','--terminal',terminal,'--json')
  processes=json.loads(process_result.stdout).get('processes',[]) if process_result.returncode==0 else []
  cli_processes=[v for v in processes if 'claude' in v.get('name','').lower() or any(Path(t).name=='claude' for t in shlex.split(v.get('command','')))]
  observed_flags=[t for v in cli_processes for t in shlex.split(v.get('command','')) if t.startswith('-')]
  result['raw_cli_choice']={'command':'claude','inference_prompt_sent':False,'provider_chrome_observed':'Claude Code' in raw_cli,'trust_prompt_observed':'Do you trust' in raw_cli,'process_query_exit':process_result.returncode,'claude_process_observed':bool(cli_processes),'observed_process_flags':observed_flags,'structured_headless_arguments_absent':not any(flag in observed_flags for flag in ['-p','--input-format','--output-format','app-server','--print'])}
  hc('keys',terminal,'ctrl+c');time.sleep(.2);hc('keys',terminal,'ctrl+c')
  result['raw_cli_choice']['cancel_keys_sent']=True
 if not args.startup_only:
  r=cmd('sheprd','chat','new','claude','--json');result['native_chat_start_exit']=r.returncode
  chat=None
  for _ in range(120):
   r=cmd('sheprd','chat','--json')
   if r.returncode==0:
    data=json.loads(r.stdout)
    for c in data.get('chats',[]):
     if c.get('attached') and c.get('shown'):chat=c;break
   if chat:break
   time.sleep(.2)
  result['native_chat_attached_and_shown']=bool(chat)
  if chat:
   ct=chat['pane_id'].removeprefix('core:')
   child_task="Reply with exactly: SHEPRD_CHILD_OK"
   parent_prompt=("Validation only. Do not read/write project files, do not edit config, and use no tools except Bash for the following three core commands. "
    "Start one child agent: "+shlex.join([str(core_bin),'run','--bg','--name','sv-child','--cwd',str(root),'claude','-p',child_task])+". "
    "Wait for sv-child using the same herdr-core executable, then read sv-child with it. Do not remove the child. "
    "The child may have a configured Stop hook that wraps its answer in prose; the literal marker SHEPRD_CHILD_OK anywhere in the output read from that child is sufficient. After observing that marker in its actual output, reply with exactly: SHEPRD_PARENT_OK SHEPRD_CHILD_OK")
   print(json.dumps({'phase':'native_parent_child','test_profile':str(root),'parent_terminal':ct,'operator_note':'Inspect any native-chat permission request; allow only the task-owned core run/wait/read commands.'}),flush=True)
   hc('send',ct,parent_prompt)
   got=False
   for _ in range(300):
    text=read(ct)
    # Only an assistant-role message in this NEW test session is a receipt.
    status=cmd('sheprd','chat','--json')
    session_ids=[]
    if status.returncode==0:
     current=json.loads(status.stdout).get('chats',[])
     session_ids=[c.get('session_id') for c in current if c.get('pane_id')==chat['pane_id']]
    for sid in session_ids:
     if not sid or not re.fullmatch(r'[A-Za-z0-9-]+',sid):continue
     for transcript in (Path.home()/'.claude/projects').glob('*/'+sid+'.jsonl'):
      prompt_seen=False
      for line in transcript.read_text().splitlines():
       try:entry=json.loads(line)
       except json.JSONDecodeError:continue
       message=entry.get('message',{})
       content=message.get('content',[])
       parts=[content] if isinstance(content,str) else [v.get('text','') for v in content if v.get('type')=='text']
       if message.get('role')=='user' and any(parent_prompt in part for part in parts):prompt_seen=True
       if prompt_seen and message.get('role')=='assistant' and any(part.strip()=='SHEPRD_PARENT_OK SHEPRD_CHILD_OK' for part in parts):got=True
    if got:break
    time.sleep(.3)
   result['native_chat_expected_reply_observed']=got
   result['native_chat_receipt_scope']='Exact assistant-role final text in the NEW own Claude test session after the known prompt; app reports native chat attached/shown. No raw transcript copied.'
   child_result=cmd('herdr-core','get','sv-child','--json')
   result['delegation_child_get_exit']=child_result.returncode
   if child_result.returncode==0:
    child=json.loads(child_result.stdout);child=child.get('terminal',child)
    result['delegation_child_record']={k:child[k] for k in ['address','name','parent','parent_id','state','exit','exit_code'] if k in child}
    child_output=read('sv-child')
    result['delegation_child_output_observed']=any('SHEPRD_CHILD_OK' in line and 'Reply with exactly' not in line for line in child_output.splitlines())
    result['delegation_lineage_matches_native_parent']=child.get('parent')==ct and child.get('exit_code')==0
   else:result['delegation_child_output_observed']=False
  else:result['native_chat_expected_reply_observed']=False
 else:result['native_chat_test']='not requested in startup-only mode'
 result['config_still_saved']=cfg.read_text().startswith('shell = ')
 result['runtime_persistent_login_honored']=shell.get('login')=='true'
 required_bool=['interactive','login','real_home','default_zdotdir','zshrc_links_dotfiles','zprofile_links_dotfiles','private_local_rc_present','private_local_rc_source_configured','rcs','globalrcs','shell_executable_matches_configured','prompt_present','binding_ctrl_a','binding_ctrl_k']+[f'export_{v}' for v in ['ASDF_DATA_DIR','GOPATH','GOBIN','GIT_PROJECTS_WORKDIR','FZF_DEFAULT_COMMAND','FZF_CTRL_T_COMMAND','FZF_DEFAULT_OPTS']]
 required_count=['gs_alias','gro_function']+[f'tool_{v}' for v in ['brew','gh','starship','direnv','fzf','zoxide','fd']]
 result['guard_checks']={
  'one_new_app_terminal':result['terminal_owned_by_test'],
  'app_window_and_tab':result['window_count']==1 and result.get('app_tab_count')==1,
  'all_required_shell_booleans':all(shell.get(k)=='true' for k in required_bool),
  'all_named_alias_function_tool_checks':all(shell.get(k)=='1' for k in required_count),
  'private_declarations_match':int(shell.get('private_declarations_detected','0'))>0 and shell.get('private_declarations_detected')==shell.get('private_declarations_defined'),
  'actual_startup_file_reads':all(result['startup_trace'].values()),
  'actual_input_edits':all(result['input'][k] for k in ['discard_marker_observed','configured_ctrl_a','configured_ctrl_k','marker_erased','expected_output_observed']),
  'saved_shell_choice':result['config_still_saved'] and result['runtime_persistent_login_honored'],
  'app_startup_external_files_unchanged':result.get('app_startup_external_files_unchanged',False)}
 if args.startup_only:
  result['guard_checks']['raw_cli_choice']=all(result['raw_cli_choice'].get(k) is True for k in ['provider_chrome_observed','claude_process_observed','structured_headless_arguments_absent']) and not result['raw_cli_choice']['inference_prompt_sent'] and not result['raw_cli_choice']['trust_prompt_observed']
 if not args.startup_only:
  result['guard_checks'].update({'native_chat_attached_and_shown':result.get('native_chat_attached_and_shown',False),'native_chat_assistant_receipt':result.get('native_chat_expected_reply_observed',False),'child_get_succeeded':result.get('delegation_child_get_exit')==0,'child_output_observed':result.get('delegation_child_output_observed',False),'child_parent_and_exit_verified':result.get('delegation_lineage_matches_native_parent',False)})
 result['result']='pass' if all(result['guard_checks'].values()) else 'partial'
 result['validation_scope']='startup/input and raw TUI choice only' if args.startup_only else 'startup/input plus native-chat and child compatibility'
except Exception as e:result['error']=type(e).__name__+': '+str(e)
finally:
 if p:
  r=cmd('sheprd','app','quit','--json');result['owned_app_quit_exit']=r.returncode
  try:p.wait(timeout=8)
  except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
  result['owned_app_exit']=p.returncode
 if core:
  r=cmd('herdr-core','server','stop','--json');result['owned_core_stop_exit']=r.returncode
 result['external_hashes_after']=hashes();result['external_files_unchanged']=before==result['external_hashes_after']
 result['external_changed_labels']=[k for k in before if before[k]!=result['external_hashes_after'][k]]
 shutil.rmtree(root);result['owned_profile_removed']=not root.exists()
 # Never persist raw terminal output or env/settings snapshots.
 result['external_config_check']={'algorithm':'SHA-256','checked_relative_paths':list(before),'unchanged_by_file':{k:before[k]==result['external_hashes_after'][k] for k in before},'all_unchanged':result['external_files_unchanged'],'unchanged_before_native_chat':before==result.get('external_hashes_before_chat',before)}
 for key in list(result):
  if key.startswith('external_hashes'):del result[key]
 out=repo/'work/evidence-2026-11-12'/('sheprd-validation-startup-guards.json' if args.startup_only else 'sheprd-validation-final.json');out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if not k.startswith('external_hashes') and k!='app_tab_list'},indent=2),flush=True)
