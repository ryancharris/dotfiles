"""Compare content digests around an isolated Paseo daemon launch; never save config contents."""
import hashlib,json,subprocess,tempfile,time,shutil
from pathlib import Path
OUT=Path(__file__).resolve().parent
BASE=Path('/Users/ryan')
PATHS=['.claude/settings.json','.claude.json','.codex/config.toml','.codex/hooks.json','.cursor/mcp.json','.gemini/settings.json','.zshrc','.zprofile','.bashrc','.config/fish/config.fish','.config/opencode/opencode.json','.config/opencode/opencode.jsonc']
def snapshots():
 records={}
 for name in PATHS:
  p=BASE/name
  records[name]=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
 skills={}
 for name in ['.claude/skills','.codex/skills','.cursor/skills']:
  root=BASE/name
  skills[name]={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()} if root.is_dir() else {}
 return records,skills
root=Path(tempfile.mkdtemp(prefix='ade-paseo-consent-',dir='/private/tmp'));home=root/'home';home.mkdir()
(home/'config.json').write_text(json.dumps({'daemon':{'listen':'127.0.0.1:6827','mcp':{'enabled':True,'injectIntoAgents':True}}}))
before,skillsbefore=snapshots()
claudebefore=json.loads((BASE/'.claude.json').read_text())
started=stopped=False
try:
 r=subprocess.run(['paseo','daemon','start','--home',str(home),'--json'],capture_output=True,text=True,timeout=40)
 started=r.returncode==0 and json.loads(r.stdout).get('action')=='started'
 if not started:raise RuntimeError('isolated launch did not succeed')
 r=subprocess.run(['paseo','daemon','stop','--home',str(home),'--json'],capture_output=True,text=True,timeout=40)
 stopped=r.returncode==0 and json.loads(r.stdout).get('action')=='stopped'
finally:
 after,skillsafter=snapshots();claudeafter=json.loads((BASE/'.claude.json').read_text())
 same={k:before[k]==after[k] for k in before};skillssame={k:skillsbefore[k]==skillsafter[k] for k in skillsbefore}
 changed_top=[k for k in set(claudebefore)|set(claudeafter) if claudebefore.get(k)!=claudeafter.get(k)]
 result={'app':'Paseo','version':'0.15.4','route':'Fresh isolated daemon home, first-party daemon start/stop, existing HOME, no inference requests or GUI events','daemon_started':started,'daemon_stopped':stopped,'config_comparison':same,'skill_tree_comparison':skillssame,'claude_json_changed_top_level_field_count':len(changed_top),'claude_json_changed_nonsecret_top_level_fields':[k if k in ['projects','mcpServers','numStartups','cachedStatsigGates','cachedGrowthBookFeatures','cachedRemoteSettings','cachedChangelog','cachedOauthInfo','lastOnboardingVersion','oauthAccount','cachedApiKey'] else 'other' for k in changed_top],'all_monitored_configs_unchanged':all(same.values()),'all_monitored_skills_unchanged':all(skillssame.values()),'scope':'Daemon-launch route only. Separate historical screenshot proves visible wizard consent. Concurrent other-app testing prevents attributing unrelated changes solely from timing.'}
 if stopped:shutil.rmtree(root);result['temporary_profile_removed']=True
 (OUT/'paseo-config-consent-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
