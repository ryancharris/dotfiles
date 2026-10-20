"""Render a Morning Coffee snapshot to self-contained HTML; stdlib only, no source access."""
from pathlib import Path
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
import argparse, html, json, re
from textwrap import shorten
from day_calendar import calendar_data, render_calendar, removal_config, _clock
from plan_submission import render_submission
from status_confirmation import pending_checks, render_confirmation_questions
from time_format import clock_label, display_snapshot, local_time
from review_state import canonical_url, review_key
from todo_state import render_todos
ASSETS=Path(__file__).resolve().parent.parent/'assets'
E=lambda x:html.escape(str(x),quote=True)
def U(url):
 if not isinstance(url,str):return '#'
 parsed=urlsplit(url)
 return url if (parsed.scheme in ('https','http') and parsed.netloc) or (url.startswith('#') and not parsed.scheme) else '#'
def A(url,label):
 if U(url)=='#':return E(label)
 return '<a target="_blank" rel="noopener noreferrer" href="'+E(U(url))+'">'+E(label)+'</a>'
def options(values,all_label):
 return '<option value="">'+E(all_label)+'</option>'+''.join('<option value="'+E(value)+'">'+E(label)+'</option>' for value,label in values)
def local_review_done(kind,url,state=None):
 try:record=(state or {}).get(review_key(kind,url),{})
 except (ValueError,TypeError):return False
 return isinstance(record,dict) and record.get('done') is True
def local_review_ui(kind,url,state=None,enabled=False):
 """Local completion is independent of source approval and queue eligibility."""
 try:
  source=canonical_url(url)
 except (ValueError,TypeError):return '', ''
 done=local_review_done(kind,source,state)
 attrs=' data-local-review data-review-kind="'+E(kind)+'" data-review-url="'+E(source)+'" data-review-done="'+str(done).lower()+'"'
 control='<div class="local-review-control"><span class="local-review-label">'+('Done locally' if done else 'To review')+'</span><button type="button" data-review-toggle aria-pressed="'+str(done).lower()+'" disabled>'+('Undo local done' if done else 'Mark done locally')+'</button><span class="local-review-message" role="status" aria-live="polite">'+('Enable JavaScript to save.' if enabled else 'Open the live Morning Coffee workspace to save.')+'</span></div>'
 return attrs,control
def section_head(title,meta=''):
 return '<div class="section-head"><h2>'+E(title)+'</h2><p class="muted">'+E(meta)+'</p></div>'
def evidence(content):
 return ''.join('<p>'+E(p)+'</p>' for p in content.get('paragraphs',[]))+('<p class="evidence-links">'+' · '.join(A(l['url'],l['label']) for l in content['links'])+'</p>' if content.get('links') else '')
def retained_notice(snapshot,section):
 stamp=snapshot.get('stale_evidence',{}).get(section)
 if not stamp:return ''
 local=local_time(stamp,snapshot['report']['timezone'],with_zone=True)
 return '<p class="retained-notice">Includes earlier evidence · last verified '+E(local)+' · refresh incomplete</p>'
def retained_row(item):
 if not item.get('_retained_at'):return ''
 stamp=datetime.fromisoformat(item['_retained_at'].replace('Z','+00:00')).strftime('%b %d, %H:%M %z')
 return '<span class="retained-row">Earlier evidence · '+E(stamp)+'</span>'
def remaining_priorities(snapshot):
 completed={str(record['id']) for record in snapshot.get('resolutions',[]) if record.get('section')=='priorities' and record.get('verified') is True and record.get('outcome') in ('completed','resolved','closed','cancelled')}
 return [row for row in snapshot['priorities'] if str(row.get('status') or 'open').lower() not in ('done','completed','resolved','cancelled') and str(row.get('id','')) not in completed]

def render_focus(snapshot,is_tea):
 rows=remaining_priorities(snapshot)
 uncertain={str(row['id']) for row in pending_checks(snapshot) if row['section']=='priorities'}
 title="🍵 What’s left" if is_tea else '☕ Today’s priorities'
 result='<section id="current-focus" class="focus-brief">'+section_head(title)+'<ol>'
 for row in rows[:3]:
  result+='<li>'+retained_row(row)+'<div><h3>'+A('#daily-priorities',shorten(row['title'],width=90,placeholder='…'))+'</h3>'+('<small class="muted">Status unconfirmed</small>' if str(row.get('id','')) in uncertain else '')+'<p>'+E(shorten(row['action'],width=150,placeholder='…'))+'</p></div></li>'
 result+='</ol>'
 if not rows:result+='<p>No verified work left to recommend.</p>'
 if len(rows)>3:result+='<a target="_blank" rel="noopener noreferrer" class="muted" href="#daily-priorities">'+str(len(rows)-3)+' more priorities</a>'
 return result+'</section>'

def render_updates(snapshot):
 updates=snapshot.get('updates')
 if not updates:return ''
 rows=sorted([row for row in updates['items'] if row['section']!='Focus & exercise'],key=lambda row:row.get('importance',5))
 new_rows=[row for row in updates.get('since_morning',[]) if row['status']=='New' and row['section'] in ('Daily priorities','Reviews waiting','RFCs to review','Today')]
 new_counts=Counter(row['section'] for row in new_rows)
 previous='Tea' if updates.get('previous_kind')=='tea-time' else 'Coffee'
 since=local_time(updates['since'],snapshot['report']['timezone'])
 result='<section id="what-changed" class="tldr">'+section_head('TL;DR', 'Since '+previous+' '+since)
 if updates.get('plan_changed'):result+='<p>Your submitted plan changed.</p>'
 if new_rows:
  names={'Daily priorities':('priority','priorities'),'Reviews waiting':('review','reviews'),'RFCs to review':('RFC','RFCs'),'Today':('event','events')}
  result+='<p class="new-since-coffee"><b>New since Coffee:</b> '+E(' · '.join(str(count)+' '+names[section][count!=1] for section,count in new_counts.items()))+'</p>'
 else:result+='<p class="muted">No verified new items since Coffee.</p>'
 if not rows and not new_rows:return result+('' if updates.get('plan_changed') else '<p>No source changes.</p>')+'</section>'
 counts=Counter(row['section'] for row in rows)
 labels={'Reviews waiting':'review update','On call & incidents':'incident update','Today':'agenda update','Daily priorities':'priority update','RFCs to review':'RFC update','Focus & exercise':'plan update'}
 summary=' · '.join(str(count)+' '+labels.get(section,section.lower())+('s' if count!=1 else '') for section,count in counts.items())
 result+='<p class="muted">'+E(summary)+'</p><ul>'
 highlights=[];seen=set()
 for row in new_rows+rows:
  key=(row['section'],row.get('id') or row.get('url') or row['title'])
  if key in seen:continue
  seen.add(key)
  if row['section']=='Focus & exercise':continue
  fields=row.get('fields',[])
  title=shorten(row['title'],width=64,placeholder='…')
  field_by_name={field['label']:field for field in fields}
  highlight=''
  if row['status']=='Resolved':highlight=title+' — resolved'
  elif row['section']=='On call & incidents' and 'Incident counts' in field_by_name:
   field=field_by_name['Incident counts'];highlight='Incidents: '+field['before']+' → '+field['after']
  elif row['section']=='Reviews waiting':
   if 'Readiness' in field_by_name and 'status: READY' in field_by_name['Readiness']['after']:
    highlight=title+' — ready for review'
   elif 'Merge status' in field_by_name:
    state=field_by_name['Merge status']['after']
    state={'UNKNOWN':'readiness unknown','DIRTY':'has conflicts','BEHIND':'behind base','BLOCKED':'blocked','CLEAN':'merge checks clear'}.get(state,state.lower())
    highlight=title+' — '+state
   elif 'Checks' in field_by_name:highlight=title+' — checks: '+field_by_name['Checks']['after']
  elif row['section']=='Daily priorities':
   if 'Priority rank' in field_by_name:highlight='Now #'+field_by_name['Priority rank']['after']+': '+title
   elif 'Status' in field_by_name:highlight=title+' — '+field_by_name['Status']['after'].lower()
   elif 'Next action' in field_by_name:highlight=title+' — '+field_by_name['Next action']['after']
   elif fields:highlight=title if fields[0]['label']=='Title' else title+' — '+fields[0]['label'].lower()+': '+fields[0]['after']
  elif row['section']=='RFCs to review':
   if field_by_name.get('Approved by you',{}).get('after')=='Yes':highlight='Approved: '+title
   elif fields:highlight=title+' — '+fields[0]['label'].lower()+': '+fields[0]['after']
  elif row['section']=='Focus & exercise':highlight='Day plan: '+row.get('after','')
  elif row['section']=='Today':
   field=field_by_name.get('Time') or (fields[0] if fields else None)
   if field:highlight=title+' — '+field['after']
  if not highlight and row['status']=='New':highlight='New: '+title
  if row['status']=='New':highlight='New: '+title
  if highlight:highlights.append(A(row.get('url') or ('#on-call' if row['section']=='On call & incidents' else '#daily-priorities' if row['section']=='Daily priorities' else '#rfcs-to-review' if row['section']=='RFCs to review' else '#focus-exercise' if row['section']=='Focus & exercise' else '#today'),shorten(highlight,width=150,placeholder='…')))
  if len(highlights)==2:break
 result+=''.join('<li>'+line+'</li>' for line in highlights)
 return result+'</ul></section>'

def render_freshness(snapshot):
 if not snapshot.get('sources'):return ''
 labels={'github':'GitHub','calendar':'Calendar','drive':'Planning','incidentio':'incident.io','notion':'Notion','slack':'Slack'}
 entries=[]
 for key,info in snapshot['sources'].items():
  stamp=local_time(info['checked_at'],snapshot['report']['timezone'],with_zone=True)
  entries.append('<li><b>'+E(labels.get(key,key))+'</b><span>'+E(info['status'])+' · checked '+E(stamp)+'</span>'+('<p>'+E(info['note'])+'</p>' if info.get('note') else '')+'</li>')
 return '<details id="source-freshness" class="source-freshness"'+'><summary>Source freshness · '+str(sum(info['status']=='complete' for info in snapshot['sources'].values()))+'/'+str(len(snapshot['sources']))+' complete</summary><ul>'+''.join(entries)+'</ul></details>'

def render_day_plan(snapshot):
 return render_calendar(snapshot)

def workspace_controls(snapshot):
 config=snapshot.get('workspace_interaction')
 if not config:return ''
 payload=json.dumps(config,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
 state=json.dumps(snapshot['workspace'],ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
 return ('<section id="workspace-controls" class="workspace-controls" aria-label="Daily workspace">'
         '<div class="workspace-actions"><button type="button" data-workspace-refresh aria-label="Refresh all sources" disabled><span aria-hidden="true" class="workspace-refresh-icon">↻</span><span data-workspace-refresh-label>Refresh</span></button>'
         '<button type="button" data-workspace-start hidden>Start today</button></div>'
         '<p data-workspace-status role="status" aria-live="polite">Source refresh is currently unavailable.</p>'
         '<script type="application/json" class="workspace-interaction-data">'+payload+'</script>'
         '<script type="application/json" class="workspace-state-data">'+state+'</script></section>')

def workspace_changes(snapshot):
 if 'workspace' not in snapshot:return ''
 rows=snapshot['workspace'].get('suggestions',[])
 result='<section id="what-changed" class="workspace-changes">'+section_head('What changed',str(len(rows))+' suggestions · your chosen work stays in place')+'<div class="workspace-suggestions">'
 for row in rows:
  item=row['item']
  result+='<article class="workspace-suggestion"><div><h3>'+A(item.get('url') or item.get('source_url'),item.get('title','Suggested work'))+'</h3><p>'+E(item.get('action',''))+'</p></div><div class="workspace-suggestion-actions"><button type="button" data-suggestion-action="accept" data-suggestion-id="'+E(row['id'])+'">Add to today</button><button type="button" data-suggestion-action="dismiss" data-suggestion-id="'+E(row['id'])+'">Dismiss</button></div></article>'
 result+='</div>'
 if not rows:result+='<p class="muted">No new work to accept.</p>'
 updates=render_updates(snapshot)
 if updates:result+='<details class="workspace-source-changes"><summary>Verified source changes</summary>'+updates.replace('id="what-changed"','id="source-changes"').replace('TL;DR','Source changes')+'</details>'
 return result+'<p class="workspace-suggestion-status" role="status" aria-live="polite"></p></section>'

def today_rows(snapshot):
 """Keep calendar evidence separate from the latest successfully saved local choices."""
 zone=ZoneInfo(snapshot['report']['timezone'])
 def minute(event):
  try:
   if event.get('all_day') or len(event['start'])==10:return -1
   start=datetime.fromisoformat(event['start'].replace('Z','+00:00'))
   start=(start.replace(tzinfo=zone) if start.tzinfo is None else start).astimezone(zone)
   return start.hour*60+start.minute
  except (KeyError,TypeError,ValueError,AttributeError):return -1
 rows=[dict(event,_local_plan=False,_minute=minute(event)) for event in snapshot['agenda']['events']]
 for block in calendar_data(snapshot,read_only=True)['submitted_blocks']:
  rows.append({'title':block['label'],'time':_clock(block['start'])+'–'+_clock(block['start']+block['minutes']),
               '_local_plan':True,'_minute':block['start'],'kind':block['kind'],'minutes':block['minutes'],'conflict':block['conflict']})
 return sorted(rows,key=lambda row:row['_minute'])

def agenda_counts(snapshot,rows):
 events=len(snapshot['agenda']['events']);chosen=sum(row['_local_plan'] for row in rows)
 return str(events)+' event'+('s' if events!=1 else '')+' from calendar · '+str(chosen)+' local plan block'+('s' if chosen!=1 else '')

def local_plan_note(row):
 return ' <span class="muted">Local chosen plan'+(' · overlaps calendar' if row.get('conflict') else '')+'</span>' if row['_local_plan'] else ''

def agenda_end(snapshot,row):
 try:
  zone=ZoneInfo(snapshot['report']['timezone'])
  if row['_local_plan']:
   minute=row['_minute']+row['minutes']
   value=datetime.fromisoformat(snapshot['report']['date']).replace(tzinfo=zone)
   from datetime import timedelta
   return (value+timedelta(minutes=minute)).isoformat()
  value=datetime.fromisoformat(row['end'].replace('Z','+00:00'))
  return (value.replace(tzinfo=zone) if value.tzinfo is None else value).isoformat()
 except (KeyError,TypeError,ValueError,AttributeError):return ''

def render_world_status(snapshot):
 reviews=snapshot['reviews']['items'];rfcs=snapshot['rfcs']['items'];counts=snapshot['oncall'].get('counts',{})
 agenda=today_rows(snapshot)
 cards=[('reviews-waiting','📮',str(len(reviews)),'Reviews',str(sum(row['queue']=='direct' for row in reviews))+' direct · '+str(sum(row['queue']=='team' for row in reviews))+' team'),
        ('rfcs-to-review','💌',str(len(rfcs)),'RFCs',str(sum(not row['user_approved'] and row.get('request_emoji')=='📨' for row in rfcs))+' requested · review decisions'),
        ('on-call','🛡️',' / '.join(str(value) for value in counts.values()) if counts else '—','Incidents',' · '.join(str(value)+' '+name for name,value in counts.items()) if counts else 'Counts unavailable'),
        ('today','🗓️',str(len(agenda)),'Agenda',agenda_counts(snapshot,agenda)+' · '+snapshot['report']['timezone'])]
 return '<nav class="world-status overview-grid" aria-label="Daily overview">'+''.join('<a target="_blank" rel="noopener noreferrer" class="status-card overview-card" href="#'+anchor+'"'+(' data-calendar-event-count="'+str(len(snapshot['agenda']['events']))+'" data-agenda-timezone="'+E(snapshot['report']['timezone'])+'"' if anchor=='today' else '')+'><span class="status-icon" aria-hidden="true">'+icon+'</span><span class="status-value">'+E(value)+'</span><span class="status-label">'+E(label)+'</span><span class="status-note">'+E(note)+'</span></a>' for anchor,icon,value,label,note in cards)+'</nav>'

def render_tea_overview(snapshot):
 """Show every domain at a glance, with source state and retained evidence intact."""
 s=snapshot
 def panel(key,anchor,title,body):
  return '<article class="check-in-card overview-card"><div class="section-head"><h3>'+E(title)+'</h3></div><p class="panel-link"><a target="_blank" rel="noopener noreferrer" href="#'+E(anchor)+'" aria-label="'+E(title+' · full view')+'">Full view ↗</a></p>'+retained_notice(s,key)+body+'</article>'
 reviews=s['reviews']['items'];direct=[row for row in reviews if row['queue']=='direct']
 shortlist=(direct+[row for row in reviews if row['queue']!='direct'])[:3]
 body='<p class="snapshot-count">'+E(str(len(reviews))+' reviews · '+str(len(direct))+' direct')+'</p><ul class="snapshot-list">'
 for row in shortlist:body+='<li>'+retained_row(row)+A(row['url'],shorten(row['title'],width=95,placeholder='…'))+'<small>'+E(row['readiness']['status'].lower()+' · '+row['repository']+'#'+str(row['number']))+'</small></li>'
 body+='</ul>' if reviews else '</ul><p>None</p>'
 cards=[panel('reviews','reviews-waiting','📮 Reviews',body)]
 total=len(s['rfcs']['items'])
 pending=[row for row in s['rfcs']['items'] if row['user_approved'] is not True and not local_review_done('rfc',row['url'],s.get('review_state'))]
 body='<div data-rfc-overview><p class="snapshot-count"><span data-rfc-overview-total>'+str(total)+' RFC'+('s' if total!=1 else '')+'</span> eligible · <span data-rfc-overview-pending>'+str(len(pending))+'</span> pending · <span data-rfc-overview-completed>'+str(total-len(pending))+'</span> approved or done</p><ul class="snapshot-list">'
 for row in pending[:3]:
  try:source_url=canonical_url(row['url'])
  except (ValueError,TypeError):source_url=''
  body+='<li data-rfc-overview-url="'+E(source_url)+'">'+retained_row(row)+A(row['url'],row['title'])+'<small>'+E(row['next_action'])+'</small></li>'
 body+='</ul><p class="muted" data-rfc-overview-note>'+('Full review list below.' if pending else 'No pending RFCs.')+'</p></div>'
 cards.append(panel('rfcs','rfcs-to-review','💌 RFC decisions',body))
 d=s['oncall'];body='<p class="snapshot-count">'+E(d['state'])+'</p><p>'+E(d['shift_label']+': '+d['shift'])+'</p><p>'+A(d['dashboard_url'],' · '.join(str(v)+' '+k for k,v in d.get('counts',{}).items()) or 'Incident counts unavailable')+'</p>'
 cards.append(panel('oncall','on-call','🛡️ On call & incidents',body))
 agenda=today_rows(s);total=len(agenda)
 body='<p class="snapshot-count">'+E(agenda_counts(s,agenda))+(' · showing 3' if total>3 else '')+'</p><ul class="snapshot-list">'
 for row in agenda[:3]:body+='<li>'+retained_row(row)+'<span class="clock">'+E(row['time'])+'</span> '+A(row.get('url'),row['title'])+local_plan_note(row)+'</li>'
 body+='</ul>' if agenda else '</ul><p>No listed events or saved plan blocks.</p>'
 cards.append(panel('agenda','today','🗓️ Agenda',body))
 body='<ul class="snapshot-list">'+''.join('<li>'+retained_row(row)+E(row['title'])+'</li>' for row in s['yesterday']['items'])+'</ul>' if s['yesterday']['items'] else '<p>No verified outcomes.</p>'
 cards.append(panel('yesterday','yesterday','🎒 Previous weekday',body))
 return '<section id="day-overview" class="brief-panel tea-overview">'+section_head('The bigger picture','A check-in across your day')+'<div class="check-in-grid overview-grid">'+''.join(cards)+'</div></section>'

def render_reviews(data,expanded=False,review_state=None,review_enabled=False):
 data={**data,'collected_label':clock_label(data['collected_label'])}
 rows=data["items"]
 personal_review=data.get('personalReview')
 personal_note=('Excluded '+str(personal_review.get('excludedCount',0))+' already approved · '+str(personal_review.get('reRequestedCount',0))+' re-requested · '+str(personal_review.get('unknownCount',0))+' approval status unknown') if personal_review is not None else ''
 approval_unknown=bool(personal_review and personal_review.get('unknownCount',0))
 roster=data.get('authorRoster') or {'status':'unavailable'}
 roster_available=roster.get('status') in ('complete','partial')
 default_authors='transport' if roster.get('status')=='complete' else 'all'
 unknown_author_count=sum(row.get('authorOnTransport') is not True and row.get('authorOnTransport') is not False for row in rows)
 author_note=roster.get('note','')
 if not roster_available:
  author_note='Transport author roster unavailable; Authors defaults to Everyone. Membership is unknown until verified.'+(' '+author_note if author_note else '')
 elif roster.get('status')=='partial':
  author_note='Transport author roster incomplete; Authors defaults to Everyone. Selecting Transport team shows only verified members.'+(' '+author_note if author_note else '')
 if roster_available and unknown_author_count:
  author_note+=((' ' if author_note else '')+str(unknown_author_count)+' requests have unknown author membership; Everyone includes them.')
 if not rows:return '<section id="reviews-waiting"><h2>Reviews waiting</h2>'+('<p class="muted">'+E(personal_note)+'</p>' if personal_note else '')+('<p class="muted">'+E(author_note)+'</p>' if author_note else '')+'<p>None</p></section>'
 controls='<div class="pr-controls" hidden><label for="pr-combined-text">Search requests<input type="search" id="pr-combined-text" data-filter="text" placeholder="Title, repository, author, details…" autocomplete="off"></label>'
 controls+='<label for="pr-combined-authors">Authors<select id="pr-combined-authors" data-filter="authors" data-default-value="'+default_authors+'"><option value="transport"'+(' selected' if default_authors=='transport' else (' disabled' if not roster_available else ''))+'>Transport team</option><option value="all"'+(' selected' if default_authors=='all' else '')+'>Everyone</option></select></label>'
 controls+='<label for="pr-combined-progress">Review progress<select id="pr-combined-progress" data-filter="progress"><option value="">All</option><option value="todo" selected>To review</option><option value="done">Done locally</option></select></label>'
 controls+='<details class="pr-extra-filters"><summary>More filters <span class="pr-filter-badge" hidden></span></summary><div class="pr-extra-filter-fields">'
 for name,label,values,alllabel in [('request-type','Request',[('direct','Direct'),('team','Team')],'All requests'),('status','Readiness',[(s,s.title()) for s in ('BLOCKED','READY','PENDING')],'All states'),('effort','Effort',[('S','Low (S)'),('M','Medium (M)'),('L','High (L)')],'All sizes'),('team','Requested team',[(t,t) for t in sorted({t for d in rows for t in d['teams']})],'All teams')]:
  controls+='<label for="pr-combined-'+name+'">'+label+'<select id="pr-combined-'+name+'" data-filter="'+name+'">'+options(values,alllabel)+'</select></label>'
 controls+='</div></details>'
 controls+='<label for="pr-combined-page-size">Rows / page<select id="pr-combined-page-size" data-page-size><option value="10">10</option><option value="25">25</option><option value="50">50</option><option value="all">All</option></select></label><button type="button" data-action="clear">Reset</button></div>'
 tr=[]
 for d in rows:
  ef=d['effort'];ci=d['ci'];author=(d.get('author') or {}).get('login')
  try:updated=local_time(d['updatedAt'],data.get('timezone','UTC'),with_date=True,with_zone=True)
  except (KeyError,ValueError,TypeError,AttributeError):updated='unavailable'
  ident=d['repository']+'#'+str(d['number'])
  state=d['mergeStateStatus']+' · '+(d['reviewDecision'] or 'No required review decision')
  cistr='CI '+str(ci['passing'])+'/'+str(ci['total'])+' completed without failure'+(' · '+str(ci['failing'])+' failing' if ci['failing'] else '')+(' · '+str(ci['pending'])+' pending' if ci['pending'] else '')+(' · '+str(ci.get('unknown',0))+' unknown' if ci.get('unknown',0) else '') if ci['total'] else 'CI unavailable' if ci['total'] is None else 'CI: no checks'
  author_membership='true' if d.get('authorOnTransport') is True else 'false' if d.get('authorOnTransport') is False else 'unknown'
  summary=d.get('summary','').strip()
  compact_summary=summary if expanded and len(summary)<=210 else ''
  review_intro='<div class="pr-summary"><p class="pr-author">'+E('Author: @'+author if author else 'Author unavailable')+'</p>'+('<p>'+E(compact_summary)+'</p>' if compact_summary else '')+'</div>'
  details=[]
  if summary and not compact_summary:details.append('<p class="pr-block"><b>TL;DR:</b> '+E(summary)+'</p>')
  driver=ef.get('driver','').strip()
  if driver and driver not in summary:details.append('<p class="pr-block"><b>Review focus:</b> '+E(driver)+'</p>')
  # Readiness evidence can carry qualifiers absent from the structured cells.
  # Suppress only exact repeated clauses; retain unfamiliar source wording.
  normalize=lambda value:re.sub(r'[^a-z0-9]+','',str(value).lower())
  shown={normalize(value) for value in [d['readiness']['status'],state,cistr,d['mergeStateStatus'],d['reviewDecision']]}
  shown.update(normalize(value) for value in cistr.split(' · '))
  if ci['total'] is not None:shown.update(normalize('CI '+str(ci['passing'])+'/'+str(ci['total'])+' '+label) for label in ('passing','passed'))
  unique_facts=[fact.strip() for fact in re.split(r';| · ',d['readiness'].get('facts','')) if fact.strip() and normalize(fact) not in shown]
  if unique_facts:details.append('<p class="pr-block"><b>Additional readiness evidence:</b> '+E('; '.join(unique_facts))+'</p>')
  if updated!='unavailable':details.append('<p class="pr-block">Updated '+E(updated)+'</p>')
  disclosure='<details class="pr-review-details"><summary>Review details</summary>'+''.join(details)+'</details>' if details else ''
  local_attrs,local_control=local_review_ui('pr',d['url'],review_state,review_enabled)
  tr.append('<tr role="row"'+local_attrs+' data-author-on-transport="'+author_membership+'" data-request-type="'+E(d['queue'])+'" data-status="'+E(d['readiness']['status'])+'" data-effort="'+E(ef['size'])+'" data-teams="'+E('|'.join(d['teams']))+'"><th scope="row" role="rowheader">'+retained_row(d)+'<a target="_blank" rel="noopener noreferrer" class="pr-heading" href="'+E(U(d['url']))+'"><span class="pr-ident">'+E(ident)+'</span>'+E(d['title'])+'</a>'+review_intro+local_control+disclosure+'</th><td role="cell"><span class="pr-type">'+('📨 Direct' if d['queue']=='direct' else 'Team request')+'</span>'+''.join('<span class="pr-team">'+E(t)+'</span>' for t in d['teams'])+'</td><td role="cell"><span class="pr-status">'+E(d['readiness']['status'])+'</span><span class="pr-facts">'+E(state)+'</span><span class="pr-facts">'+E(cistr)+'</span></td><td role="cell"><span class="effort-label"><span class="size-glyph" data-size="'+E(ef['size'])+'" aria-hidden="true"><i></i><i></i><i></i></span>'+E(ef['label'])+'</span><span class="effort-numbers">'+E(ef['inputs'])+'</span></td></tr>')

 def distribution(label,counts):
  total=sum(counts.values()); accessible=label+': '+', '.join(str(v)+' '+k for k,v in counts.items())
  return '<div class="distribution"><span class="metric-label">'+E(label)+'</span><span class="dist-bar" role="img" aria-label="'+E(accessible)+'">'+''.join('<i style="width:'+str(round(v/(total or 1)*100,3))+'%"></i>' for v in counts.values())+'</span><span class="dist-key">'+''.join('<span><b>'+str(v)+'</b> '+E(k)+'</span>' for k,v in counts.items())+'</span></div>'
 statuses=Counter(d['readiness']['status'] for d in rows);sizes=Counter(d['effort']['size'] for d in rows)
 pr='<section id="reviews-waiting"><div class="section-head"><h2>Reviews waiting <span class="muted">'+str(len(rows))+'</span></h2><p class="muted">All retained requests · oldest updated first · '+E(data['collected_label'])+'</p></div>'+('<p class="muted" role="status">'+E(personal_note)+'</p>' if approval_unknown else '')+('<p class="muted" role="status">'+E(author_note)+'</p>' if author_note and (roster.get('status')!='complete' or unknown_author_count) else '')+'<div class="review-overview">'+distribution('Readiness',{k.lower():statuses[k] for k in ('BLOCKED','READY','PENDING')})+distribution('Effort',{k:sizes[k] for k in ('S','M','L')})+'</div><div class="pr-queue" id="pr-combined">'+controls+'<p class="pr-count" role="status" aria-live="polite">'+str(len(rows))+' retained requests · JavaScript unavailable: all retained rows shown; author filter and pagination inactive</p><div class="pr-scroll" role="region" aria-label="Reviews waiting table"><table class="pr-table" role="table"><caption>'+str(sum(d['queue']=='direct' for d in rows))+' direct · '+str(sum(d['queue']=='team' for d in rows))+' team · '+str(len(rows))+' total · oldest updated first. Review effort includes exact file, commit and line-change inputs.</caption><colgroup><col><col><col><col></colgroup><thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Pull request / author / details</th><th scope="col" role="columnheader">Requested via</th><th scope="col" role="columnheader">Readiness</th><th scope="col" role="columnheader">Review effort</th></tr></thead><tbody role="rowgroup">'+''.join(tr)+'</tbody></table></div><p class="pr-empty" hidden>No requests match these filters. Choose Everyone in Authors and All in Review progress, or reset other filters to broaden the results.</p><nav class="pr-pagination" aria-label="Reviews waiting pages" hidden><button type="button" data-action="previous">← Previous</button><span class="pr-page" role="status" aria-live="polite"></span><button type="button" data-action="next">Next →</button></nav></div><details class="review-queue-notes"><summary>Queue coverage &amp; sources</summary>'+('<p class="muted">'+E(personal_note)+'</p>' if personal_note and not approval_unknown else '')+('<p class="muted">'+E(author_note)+'</p>' if author_note and roster.get('status')=='complete' and not unknown_author_count else '')+'<p class="pr-sources">Source queries: '+ ' · '.join(A(s['url'],s['label']) for s in data['scopes'])+'</p></details></section>'
 return pr
def render(snapshot):
 if snapshot.get('schema_version') != 1:raise ValueError('Unsupported snapshot schema_version')
 snapshot=display_snapshot(snapshot)
 s=snapshot;r=s['report'];parts=[];workspace='workspace' in s;is_tea=s.get('history',{}).get('kind')=='tea-time' and not workspace;theme='tea' if is_tea else 'coffee'
 if workspace:r=dict(r,title='Morning Coffee',page_title='Morning Coffee · '+r['date'])
 parts.append('<header class="shop-sign"><div class="brand-lockup"><span class="pixel-mascot '+('tea-sprite' if is_tea else 'coffee-sprite')+'" aria-hidden="true"></span><div class="brand-copy"><p class="eyebrow">'+('🫖 TEA BREAK · DAY CHECKPOINT' if is_tea else '☕ COFFEE CLUB · DAILY OVERVIEW')+'</p><h1>'+E(r['title'])+'</h1><p class="brand-subtitle">'+('A little pause. The whole day in view.' if is_tea else 'Your day, gathered in one cozy place.')+' <span class="kaomoji" aria-hidden="true">'+('( ˘▾˘)っ🍵' if is_tea else '(｡•ᴗ•｡)っ☕')+'</span></p></div></div><p class="date"><b>'+E(r['date'])+'</b>'+('Steeped at ' if is_tea else 'Brewed at ')+E(r['time']+' · '+r['timezone'])+'<br>'+E(r.get('preview_label',''))+'</p></header>')
 parts.append(workspace_controls(s))
 warnings=s.get('history',{}).get('warnings',[])
 if is_tea:
  parts.append(render_focus(s,True))
  parts.append(render_updates(s))
 else:parts.append(render_world_status(s))
 parts.append(workspace_changes(s))
 incomplete=[key for key,value in s.get('sources',{}).items() if value['status']!='complete']
 coverage=[]
 if incomplete:coverage.append('Partial coverage: '+', '.join(incomplete))
 if s.get('stale_sections'):coverage.append('Earlier evidence retained')
 if warnings:coverage.append('History recovery: '+str(len(warnings))+' saved report(s) skipped')
 parts.append('<p id="workspace-coverage" class="coverage concise-coverage"'+('' if coverage else ' hidden')+'>'+E(' · '.join(coverage))+(' · '+A('#source-freshness','Details') if coverage else '')+'</p>')
 if is_tea:parts.append(render_confirmation_questions(s))
 if is_tea:parts.append(render_tea_overview(s))
 day_context_position=len(parts)
 parts.append(render_todos(s))
 priority_position=len(parts)
 calendar=render_calendar(s,read_only=is_tea)
 if not is_tea:calendar=calendar.replace('<div id="coffee-confirmation"></div>','<div id="coffee-confirmation">'+render_submission(s)+'</div>')
 parts.append(calendar)
 parts.append('<details id="full-context" class="full-brief"><summary>Complete queues &amp; source evidence</summary>' if is_tea else '<div id="coffee-context" class="brief-dashboard context-grid">')
 source_notes=[render_freshness(s)]
 if s.get('availability',{}).get('coverage'):source_notes.append('<p class="muted">Calendar evidence: '+E(s['availability']['coverage'])+'</p>')
 if s.get('coverage'):source_notes.append('<p class="muted">'+E(s['coverage'])+'</p>')
 if warnings:source_notes.append('<details><summary>History recovery details</summary><ul>'+''.join('<li>'+E(warning)+'</li>' for warning in warnings)+'</ul></details>')
 priorities='<section id="daily-priorities">'+section_head('Daily priorities',str(len(s['priorities']))+' outcomes to drive today · evidence-backed recommendations')+'<ol class="priority-ledger">'
 for i,d in enumerate(s['priorities'],1):
  priorities+='<li class="priority-row"><span class="priority-num" aria-hidden="true">'+str(i).zfill(2)+'</span><div>'+retained_row(d)+'<h3>'+E(d['title'])+'</h3><p class="priority-context">'+E(d['context'])+'</p></div><div class="priority-action">'+E(d['action'])+'<details><summary>Evidence &amp; context</summary>'+evidence(d['evidence'])+'</details></div><div class="priority-done"><b>Done when</b>'+E(d['done'])+'</div></li>'
 priorities+=('</ol>' if s['priorities'] else '</ol><p>None</p>')+'</section>'
 if is_tea:parts.append(priorities)
 else:parts.insert(priority_position,priorities)
 if s.get('unverified_priorities'):
  parts.append('<details class="retained-notice"><summary>Earlier priorities to recheck · '+str(len(s['unverified_priorities']))+'</summary>'+''.join('<article>'+retained_row(item)+'<h3>'+E(item['title'])+'</h3><p>'+E(item['action'])+'</p>'+evidence(item['evidence'])+'</article>' for item in s['unverified_priorities'])+'</details>')
 d=s['agenda'];rows=today_rows(s)
 saved_plan=calendar_data(s)['submitted_at'] is not None if not is_tea else False
 edit_schedule=('<button type="button" data-edit-schedule aria-controls="focus-exercise" aria-expanded="'+str(not saved_plan).lower()+'"'+('' if saved_plan else ' hidden')+'>Edit schedule</button>') if not is_tea else ''
 agenda='<section id="today">'+section_head('Today',d['coverage'])+edit_schedule+'<ul class="agenda">'
 removal=removal_config(s) if workspace else None
 for event in rows:
  end=agenda_end(s,event)
  end_attr=(' data-'+('local-plan-end' if event['_local_plan'] else 'calendar-end')+'="'+E(end)+'"') if end else ''
  remove=('<button type="button" class="today-remove-plan day-remove-submitted" data-kind="'+E(event['kind'])+'" data-start="'+str(event['_minute'])+'" data-minutes="'+str(event['minutes'])+'" aria-label="Remove '+E(event['title'])+' from your local plan">Remove</button>') if removal and event['_local_plan'] else ''
  agenda+='<li data-plan-source="'+('local' if event['_local_plan'] else 'calendar')+'" data-start="'+str(event['_minute'])+'"'+end_attr+'><span class="clock">'+E(event['time'])+'</span><span>'+retained_row(event)+A(event.get('url'),event['title'])+local_plan_note(event)+(' <span class="muted">free</span>' if event.get('free') else '')+(' <span class="muted">tentative</span>' if event.get('tentative') else '')+'</span><span class="join">'+(A(event['join_url'],event.get('join_label','Join call')+' ↗') if event.get('join_url') else '')+remove+'</span></li>'
 agenda+='</ul><p class="agenda-empty"'+(' hidden' if rows else '')+'>None</p></section>'
 if removal:
  payload=json.dumps(removal,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
  agenda=agenda.replace('</section>','<p class="day-remove-status" role="status" aria-live="polite"></p><script type="application/json" class="day-plan-removal-data">'+payload+'</script></section>')
 if is_tea:parts.append(agenda)
 d=s['oncall'];countlabel='Incidents dashboard: '+', '.join(str(v)+' '+k for k,v in d.get('counts',{}).items())
 oncall='<section id="on-call">'+section_head('On call & incidents',d['schedule'])+'<div class="oncall-strip"><div class="oncall-state"><span class="oncall-dot" aria-hidden="true"></span>'+E(d['state'])+' <span class="muted">'+E(d['responder'])+'</span></div><p class="oncall-next"><b>'+E(d['shift_label'])+':</b> '+E(d['shift'])+'</p>'
 oncall+='<a target="_blank" rel="noopener noreferrer" class="incident-counts" href="'+E(U(d['dashboard_url']))+'" aria-label="'+E(countlabel)+'">'+''.join('<span><b>'+str(v)+'</b> '+E(k)+'</span>' for k,v in d.get('counts',{}).items())+'</a></div><p class="muted oncall-note">'+E(d['note'])+'</p></section>'
 if is_tea:parts.append(oncall)
 else:parts.insert(day_context_position,'<div id="day-context" class="brief-dashboard context-grid">'+agenda+oncall+'</div>')
 d=s['rfcs'];pending_rfcs=[];completed_rfcs=[]
 for index,item in enumerate(d['items']):
  display_id=item['id'] if not str(item['id']).startswith(('https://','http://')) and not item['title'].startswith(str(item['id'])) else ''
  local_attrs,local_control=local_review_ui('rfc',item['url'],s.get('review_state'),bool(s.get('review_interaction')))
  locally_done=local_review_done('rfc',item['url'],s.get('review_state'))
  approved=item['user_approved'] is True
  row='<article class="rfc-row"'+local_attrs+' data-source-approved="'+str(approved).lower()+'" data-review-order="'+str(index)+'"><div>'+retained_row(item)+'<h3>'+A(item['url'],(display_id+' · ' if display_id else '')+item['title'])+(' ✓' if approved else '')+'</h3><p class="rfc-relationship">'+E(item['request_emoji']+' '+item['request_label'])+'</p><p class="rfc-meta">'+E((item['author'] or 'Author unavailable')+' · submitted '+item['submitted_local'])+'</p>'+('<p class="rfc-summary">'+E(item['summary'])+'</p>' if not is_tea else '')+'</div><div class="rfc-next">'+E(item['next_action'])+'<details><summary>Proposal &amp; evidence</summary>'+('<p>'+E(item['summary'])+'</p>' if is_tea else '')+'<p>'+E(item['relationship'])+'</p><p class="evidence-links">'+A(item['url'],'Read proposal')+(' · '+A(item['approval_url'],'Approval record') if item.get('approval_url') else '')+'</p></details></div><div class="rfc-state"><b>'+E(item['approval_status'] or 'No direct review request found')+'</b><p>'+('✓ Approved by you' if approved else 'No verified approval from you')+'</p>'+local_control+'</div></article>'
  (completed_rfcs if approved or locally_done else pending_rfcs).append(row)
 rfc='<section id="rfcs-to-review"><div class="section-head"><h2>RFCs to review <span class="muted" data-rfc-pending-count>'+str(len(pending_rfcs))+'</span></h2><p class="muted">'+str(len(d['items']))+' eligible · '+E(d['window_label'])+' · '+A(d['database_url'],'Database ↗')+'</p></div><p class="rfc-group-status" data-rfc-group-status role="status" aria-live="polite"></p><div class="rfc-list" data-rfc-pending>'+''.join(pending_rfcs)+'</div><p data-rfc-empty'+(' hidden' if pending_rfcs else '')+'>No pending RFCs.</p>'
 rfc+='<details class="rfc-completed" data-rfc-completed'+('' if completed_rfcs else ' hidden')+'><summary>Approved or done (<span data-rfc-completed-count>'+str(len(completed_rfcs))+'</span>)</summary><div class="rfc-list" data-rfc-completed-list>'+''.join(completed_rfcs)+'</div></details>'
 parts.append(rfc+'<div class="section-head rfc-coverage"><p class="legend">📨 Direct request &nbsp; 👀 Optional &nbsp; ✓ Your verified approval</p><details><summary>'+E(d['coverage_label'])+'</summary><p>'+E(d['coverage'])+'</p></details></div></section>')
 parts.append(render_reviews({**s['reviews'],'timezone':r['timezone']},expanded=not is_tea,review_state=s.get('review_state'),review_enabled=bool(s.get('review_interaction'))))
 d=s['yesterday'];yesterday='<section id="yesterday">'+section_head('Yesterday',d['date'])+'<div class="yesterday-list">'
 for item in d['items']:
  yesterday+='<article>'+retained_row(item)+'<h3>'+E(item['title'])+'</h3>'+(evidence(item['content']) if not is_tea else '<details><summary>Outcome, unresolved work &amp; sources</summary>'+evidence(item['content'])+'</details>')+'</article>'
 parts.append(yesterday+'</div>'+('' if d['items'] else '<p>None</p>')+'<details class="foot-note"><summary>Activity coverage</summary><p>'+E(d['coverage'])+'</p></details></section>')
 parts.append('<section id="source-notes" class="source-notes">'+section_head('Source notes')+''.join(source_notes)+'</section>')
 parts.append('</details>' if is_tea else '</div>')
 for key,anchor in [('priorities','daily-priorities'),('agenda','today'),('oncall','on-call'),('rfcs','rfcs-to-review'),('reviews','reviews-waiting'),('yesterday','yesterday')]:
  notice=retained_notice(s,key)
  if notice:parts=[part.replace('<section id="'+anchor+'">','<section id="'+anchor+'">'+notice,1) for part in parts]
 css=(ASSETS/'brief.css').read_text();js=(ASSETS/'brief.js').read_text()
 config=s.get('review_interaction')
 if config:
  serialized=json.dumps(config,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
  parts.append('<script type="application/json" class="review-interaction-data">'+serialized+'</script>')
 js+=(ASSETS/'local-review-state.js').read_text()
 css+=(ASSETS/'local-todo.css').read_text()
 css+=(ASSETS/'project-tag-picker.css').read_text()
 js+=(ASSETS/'project-tag-picker.js').read_text()
 js+=(ASSETS/'local-todo.js').read_text()
 css+=(ASSETS/'day-calendar.css').read_text()
 css+=(ASSETS/'layout.css').read_text()
 css+=(ASSETS/'typography.css').read_text()
 js+=(ASSETS/'day-calendar.js').read_text()
 if not is_tea:js+=(ASSETS/'local-plan-submission.js').read_text()
 css+=(ASSETS/'calendar-past.css').read_text()
 js+=(ASSETS/'calendar-past.js').read_text()
 if workspace:
  css+=(ASSETS/'workspace.css').read_text()
  js+=(ASSETS/'workspace.js').read_text()
 return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+E(r['page_title'])+'</title><style>'+css+'</style></head><body class="'+theme+'"><main>'+''.join(parts)+'</main><script>'+js+'</script></body></html>'
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('snapshot',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
 args.output.write_text(render(json.loads(args.snapshot.read_text())))
 print(args.output)
