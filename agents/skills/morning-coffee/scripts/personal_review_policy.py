"""Read-only personal review eligibility; no head-SHA-based invalidation."""
from datetime import datetime

def stamp(value):
 return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

def personal_review_decision(reviews,login,current_requests,relevant_team_slugs,timeline=None,timeline_complete=False):
 result={'userLogin':login,'state':'NONE','latestEffectiveReview':None,'personalReviews':[], 'excluded':False,'reRequested':False,'reRequestEvidence':None,'coverage':'complete','timelineCoverage':'not required','reason':'No personal actionable review exists.'}
 if not isinstance(reviews,list):
  return {**result,'state':'UNKNOWN','coverage':'incomplete','reason':'Personal review history unavailable; candidate retained.'}
 mine=[r for r in reviews if (r.get('user',{}).get('login') or '').casefold()==login.casefold()]
 result['personalReviews']=mine
 actionable=[r for r in mine if r.get('state') in ('APPROVED','CHANGES_REQUESTED','DISMISSED')]
 try: actionable.sort(key=lambda r:(stamp(r['submitted_at']),r['id']))
 except (ValueError,KeyError,TypeError,AttributeError):
  return {**result,'state':'UNKNOWN','coverage':'incomplete','reason':'Personal review order unavailable; candidate retained.'}
 if not actionable:return result
 latest=actionable[-1];result['latestEffectiveReview']=latest;result['state']=latest['state']
 if latest['state']!='APPROVED':
  result['reason']='Latest effective personal review is '+latest['state']+'; candidate retained.';return result
 if (not isinstance(current_requests,dict) or 'error' in current_requests
     or not isinstance(current_requests.get('users'),list)
     or not isinstance(current_requests.get('teams'),list)):
  return {**result,'coverage':'incomplete','timelineCoverage':'not checked','reason':'Current request targets unavailable; approved candidate retained.'}
 if not timeline_complete or not isinstance(timeline,list):
  return {**result,'coverage':'incomplete','timelineCoverage':'incomplete','reason':'Approval known but re-request timeline unavailable; candidate retained.'}
 result['timelineCoverage']='complete'
 current_user=any((u.get('login') or '').casefold()==login.casefold() for u in current_requests.get('users',[]))
 relevant_slugs={s.casefold() for s in relevant_team_slugs}
 current_teams={str(t.get('id')):t for t in current_requests.get('teams',[]) if (t.get('slug') or '').casefold() in relevant_slugs}
 current_team_slugs={(t.get('slug') or '').casefold():t for t in current_teams.values()}
 try:
  events=sorted([e for e in timeline if e.get('event')=='review_requested'],key=lambda e:(stamp(e['created_at']),e.get('id',0)))
  for event in events:
   if stamp(event['created_at'])<=stamp(latest['submitted_at']):continue
   reviewer=event.get('requested_reviewer') or {};team=event.get('requested_team') or (reviewer if reviewer.get('slug') else {})
   target=None
   if current_user and (reviewer.get('login') or '').casefold()==login.casefold():target={'type':'user','login':login}
   elif team and (str(team.get('id')) in current_teams or (team.get('slug') or '').casefold() in current_team_slugs):target={'type':'team','slug':team.get('slug'),'id':team.get('id'),'name':team.get('name')}
   if target:result['reRequestEvidence']={'id':event.get('id'),'nodeId':event.get('node_id'),'createdAt':event['created_at'],'actor':(event.get('actor') or {}).get('login'),'target':target}
 except (ValueError,KeyError,TypeError,AttributeError):
  return {**result,'coverage':'incomplete','timelineCoverage':'incomplete','reason':'Re-request timeline ordering unavailable; approved candidate retained.'}
 if result['reRequestEvidence']:
  result['reRequested']=True;result['reason']='Explicit review_requested event after latest personal approval targets a currently requested user/team; candidate retained.'
 else:
  result['excluded']=True;result['reason']='Already personally APPROVED with no later explicit re-request to a current relevant target.'
 return result
