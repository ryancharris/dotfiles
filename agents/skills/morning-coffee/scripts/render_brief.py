"""Render a Morning Coffee snapshot to self-contained HTML; stdlib only, no source access."""
from pathlib import Path
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
import argparse, html, json
ASSETS=Path(__file__).resolve().parent.parent/'assets'
E=lambda x:html.escape(str(x),quote=True)
def U(url):
 if not isinstance(url,str):return '#'
 parsed=urlsplit(url)
 return url if (parsed.scheme in ('https','http') and parsed.netloc) or (url.startswith('#') and not parsed.scheme) else '#'
def A(url,label):
 if U(url)=='#':return E(label)
 return '<a href="'+E(U(url))+'">'+E(label)+'</a>'
def options(values,all_label):
 return '<option value="">'+E(all_label)+'</option>'+''.join('<option value="'+E(value)+'">'+E(label)+'</option>' for value,label in values)
def section_head(title,meta=''):
 return '<div class="section-head"><h2>'+E(title)+'</h2><p class="muted">'+E(meta)+'</p></div>'
def evidence(content):
 return ''.join('<p>'+E(p)+'</p>' for p in content.get('paragraphs',[]))+('<p class="evidence-links">'+' · '.join(A(l['url'],l['label']) for l in content['links'])+'</p>' if content.get('links') else '')
def render_reviews(data):
 rows=data["items"]
 personal_review=data.get('personalReview')
 personal_note=('Excluded '+str(personal_review.get('excludedCount',0))+' already approved · '+str(personal_review.get('reRequestedCount',0))+' re-requested · '+str(personal_review.get('unknownCount',0))+' approval status unknown') if personal_review is not None else ''
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
 for name,label,values,alllabel in [('request-type','Request',[('direct','Direct'),('team','Team')],'All requests'),('status','Readiness',[(s,s.title()) for s in ('BLOCKED','READY','PENDING')],'All states'),('effort','Effort',[('S','Low (S)'),('M','Medium (M)'),('L','High (L)')],'All sizes'),('team','Requested team',[(t,t) for t in sorted({t for d in rows for t in d['teams']})],'All teams')]:
  controls+='<label for="pr-combined-'+name+'">'+label+'<select id="pr-combined-'+name+'" data-filter="'+name+'">'+options(values,alllabel)+'</select></label>'
 controls+='<label for="pr-combined-page-size">Rows / page<select id="pr-combined-page-size" data-page-size><option value="10">10</option><option value="25">25</option><option value="50">50</option><option value="all">All</option></select></label><button type="button" data-action="clear">Reset</button></div>'
 tr=[]
 for d in rows:
  ef=d['effort'];ci=d['ci'];author=(d.get('author') or {}).get('login')
  try:updated=datetime.fromisoformat(d['updatedAt'].replace('Z','+00:00')).astimezone(ZoneInfo(data.get('timezone','UTC'))).strftime('%b %-d, %-I:%M %p %Z')
  except (KeyError,ValueError,TypeError,AttributeError):updated='unavailable'
  ident=d['repository']+'#'+str(d['number'])
  state=d['mergeStateStatus']+' · '+(d['reviewDecision'] or 'No required review decision')
  cistr='CI '+str(ci['passing'])+'/'+str(ci['total'])+' completed without failure'+(' · '+str(ci['failing'])+' failing' if ci['failing'] else '')+(' · '+str(ci['pending'])+' pending' if ci['pending'] else '')+(' · '+str(ci.get('unknown',0))+' unknown' if ci.get('unknown',0) else '') if ci['total'] else 'CI unavailable' if ci['total'] is None else 'CI: no checks'
  author_membership='true' if d.get('authorOnTransport') is True else 'false' if d.get('authorOnTransport') is False else 'unknown'
  tr.append('<tr role="row" data-author-on-transport="'+author_membership+'" data-request-type="'+E(d['queue'])+'" data-status="'+E(d['readiness']['status'])+'" data-effort="'+E(ef['size'])+'" data-teams="'+E('|'.join(d['teams']))+'"><th scope="row" role="rowheader"><a class="pr-heading" href="'+E(U(d['url']))+'"><span class="pr-ident">'+E(ident)+'</span>'+E(d['title'])+'</a><details><summary>Review details <span class="pr-author">'+E('Author: @'+author if author else 'Author unavailable')+'</span></summary><span class="pr-block"><b>TL;DR:</b> '+E(d['summary'])+'</span><span class="pr-block"><b>Review effort:</b> '+E(ef['label']+' — '+ef['inputs']+'. '+ef['driver'])+'</span><span class="pr-block"><b>Readiness:</b> '+E(d['readiness']['facts'])+'</span><span class="pr-block">Updated '+E(updated)+'</span></details></th><td role="cell"><span class="pr-type">'+('📨 Direct' if d['queue']=='direct' else 'Team request')+'</span>'+''.join('<span class="pr-team">'+E(t)+'</span>' for t in d['teams'])+'</td><td role="cell"><span class="pr-status">'+E(d['readiness']['status'])+'</span><span class="pr-facts">'+E(state)+'</span><span class="pr-facts">'+E(cistr)+'</span></td><td role="cell"><span class="effort-label"><span class="size-glyph" data-size="'+E(ef['size'])+'" aria-hidden="true"><i></i><i></i><i></i></span>'+E(ef['label'])+'</span><span class="effort-numbers">'+str(d['changedFiles'])+'f · '+str(d.get('commitCount',len(d.get('commits',[]))))+'c<br>+'+str(d['additions'])+' / −'+str(d['deletions'])+'</span></td></tr>')

 def distribution(label,counts):
  total=sum(counts.values()); accessible=label+': '+', '.join(str(v)+' '+k for k,v in counts.items())
  return '<div class="distribution"><span class="metric-label">'+E(label)+'</span><span class="dist-bar" role="img" aria-label="'+E(accessible)+'">'+''.join('<i style="width:'+str(round(v/(total or 1)*100,3))+'%"></i>' for v in counts.values())+'</span><span class="dist-key">'+''.join('<span><b>'+str(v)+'</b> '+E(k)+'</span>' for k,v in counts.items())+'</span></div>'
 statuses=Counter(d['readiness']['status'] for d in rows);sizes=Counter(d['effort']['size'] for d in rows)
 pr='<section id="reviews-waiting"><div class="section-head"><h2>Reviews waiting <span class="muted">'+str(len(rows))+'</span></h2><p class="muted">All retained requests · oldest updated first · '+E(data['collected_label'])+'</p></div>'+('<p class="muted">'+E(personal_note)+'</p>' if personal_note else '')+('<p class="muted" role="status">'+E(author_note)+'</p>' if author_note else '')+'<div class="review-overview">'+distribution('Readiness',{k.lower():statuses[k] for k in ('BLOCKED','READY','PENDING')})+distribution('Effort',{k:sizes[k] for k in ('S','M','L')})+'</div><div class="pr-queue" id="pr-combined">'+controls+'<p class="pr-count" role="status" aria-live="polite">'+str(len(rows))+' retained requests · JavaScript unavailable: all retained rows shown; author filter and pagination inactive</p><div class="pr-scroll" role="region" aria-label="Reviews waiting table"><table class="pr-table" role="table"><caption>'+str(sum(d['queue']=='direct' for d in rows))+' direct · '+str(sum(d['queue']=='team' for d in rows))+' team · '+str(len(rows))+' total · oldest updated first. Size inputs: f means files; c means commits; plus and minus are line changes.</caption><colgroup><col><col><col><col></colgroup><thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Pull request / author / details</th><th scope="col" role="columnheader">Requested via</th><th scope="col" role="columnheader">Readiness</th><th scope="col" role="columnheader">Review effort</th></tr></thead><tbody role="rowgroup">'+''.join(tr)+'</tbody></table></div><p class="pr-empty" hidden>No requests match these filters. Choose Everyone in Authors or reset other filters to broaden the results.</p><nav class="pr-pagination" aria-label="Reviews waiting pages" hidden><button type="button" data-action="previous">← Previous</button><span class="pr-page" role="status" aria-live="polite"></span><button type="button" data-action="next">Next →</button></nav></div><p class="pr-sources">'+str(sum(d['queue']=='direct' for d in rows))+' direct · '+str(sum(d['queue']=='team' for d in rows))+' team · f = files, c = commits · Source queries: '+ ' · '.join(A(s['url'],s['label']) for s in data['scopes'])+'</p></section>'
 return pr
def render(snapshot):
 if snapshot.get('schema_version') != 1:raise ValueError('Unsupported snapshot schema_version')
 s=snapshot;r=s['report'];parts=[]
 parts.append('<header><div><p class="eyebrow">'+E(r['eyebrow'])+'</p><h1>'+E(r['title'])+'</h1></div><p class="date"><b>'+E(r['date'])+'</b>'+E(r['time']+' · '+r['timezone'])+'<br>'+E(r.get('preview_label',''))+'</p></header>')
 coverage=s.get('coverage','')
 roster=(s.get('reviews') or {}).get('authorRoster') or {'status':'unavailable'}
 if roster.get('status') not in ('complete','partial'):
  coverage+=(' ' if coverage else '')+'Transport author roster unavailable; reviews default to Everyone.'
 elif roster.get('status')=='partial':
  coverage+=(' ' if coverage else '')+'Transport author roster incomplete; reviews default to Everyone.'
 if coverage:parts.append('<div class="coverage"><b>Coverage:</b> '+E(coverage)+' '+A('#yesterday','Activity coverage')+'</div>')
 counts=[('daily-priorities',len(s['priorities']),'Daily priorities'),('today',len(s['agenda']['events']),'Today’s events'),('rfcs-to-review',len(s['rfcs']['items']),'RFCs in review'),('reviews-waiting',len(s['reviews']['items']),'PR requests')]
 parts.append('<nav class="section-nav" aria-label="Brief sections">'+''.join('<a href="#'+key+'"><strong>'+str(n).zfill(2)+'</strong><span>'+E(label)+'</span></a>' for key,n,label in counts)+'</nav>')
 priorities='<section id="daily-priorities">'+section_head('Daily priorities',str(len(s['priorities']))+' outcomes to drive today · evidence-backed recommendations')+'<ol class="priority-ledger">'
 for i,d in enumerate(s['priorities'],1):
  priorities+='<li class="priority-row"><span class="priority-num" aria-hidden="true">'+str(i).zfill(2)+'</span><div><h3>'+E(d['title'])+'</h3><p class="priority-context">'+E(d['context'])+'</p></div><div class="priority-action">'+E(d['action'])+'<details><summary>Evidence &amp; context</summary>'+evidence(d['evidence'])+'</details></div><div class="priority-done"><b>Done when</b>'+E(d['done'])+'</div></li>'
 parts.append(priorities+('</ol>' if s['priorities'] else '</ol><p>None</p>')+'</section>')
 if s.get('okr'):
  d=s['okr'];parts.append('<p class="okr"><b>OKRs</b> '+A(d['url'],d['label'])+' · '+E(d['period'])+'</p>')
 d=s['agenda'];agenda='<section id="today">'+section_head('Today',d['coverage'])+'<ul class="agenda">'
 for event in d['events']:
  agenda+='<li><span class="clock">'+E(event['time'])+'</span><span>'+A(event.get('url'),event['title'])+(' <span class="muted">free</span>' if event.get('free') else '')+(' <span class="muted">tentative</span>' if event.get('tentative') else '')+'</span><span class="join">'+(A(event['join_url'],event.get('join_label','Join call')+' ↗') if event.get('join_url') else '')+'</span></li>'
 parts.append(agenda+'</ul>'+('' if d['events'] else '<p>None</p>')+'</section>')
 d=s['oncall'];countlabel='Incidents dashboard: '+', '.join(str(v)+' '+k for k,v in d.get('counts',{}).items())
 oncall='<section id="on-call">'+section_head('On call & incidents',d['schedule'])+'<div class="oncall-strip"><div class="oncall-state"><span class="oncall-dot" aria-hidden="true"></span>'+E(d['state'])+' <span class="muted">'+E(d['responder'])+'</span></div><p class="oncall-next"><b>'+E(d['shift_label'])+':</b> '+E(d['shift'])+'</p>'
 oncall+='<a class="incident-counts" href="'+E(U(d['dashboard_url']))+'" aria-label="'+E(countlabel)+'">'+''.join('<span><b>'+str(v)+'</b> '+E(k)+'</span>' for k,v in d.get('counts',{}).items())+'</a></div><p class="muted oncall-note">'+E(d['note'])+'</p></section>';parts.append(oncall)
 d=s['rfcs'];rfc='<section id="rfcs-to-review"><div class="section-head"><h2>RFCs to review <span class="muted">'+str(len(d['items']))+'</span></h2><p class="muted">'+E(d['window_label'])+' · '+A(d['database_url'],'Database ↗')+'</p></div><div class="rfc-list">'
 for item in d['items']:
  rfc+='<article class="rfc-row"><div><h3>'+A(item['url'],item['id']+' · '+item['title'])+(' ✓' if item['user_approved'] else '')+'</h3><p class="rfc-relationship">'+E(item['request_emoji']+' '+item['request_label'])+'</p><p class="rfc-meta">'+E(item['author']+' · submitted '+item['submitted_local'])+'</p></div><div class="rfc-next">'+E(item['next_action'])+'<details><summary>Proposal &amp; evidence</summary><p>'+E(item['summary'])+'</p><p>'+E(item['relationship'])+'</p><p class="evidence-links">'+A(item['url'],'Read proposal')+(' · '+A(item['approval_url'],'Approval record') if item.get('approval_url') else '')+'</p></details></div><div class="rfc-state"><b>'+E(item['approval_status'] or 'No direct review request found')+'</b><p>'+('✓ Approved by you' if item['user_approved'] else 'No verified approval from you')+'</p></div></article>'
 parts.append(rfc+'</div>'+('' if d['items'] else '<p>None</p>')+'<div class="section-head rfc-coverage"><p class="legend">📨 Direct request &nbsp; 👀 Optional &nbsp; ✓ Your verified approval</p><details><summary>'+E(d['coverage_label'])+'</summary><p>'+E(d['coverage'])+'</p></details></div></section>')
 parts.append(render_reviews({**s['reviews'],'timezone':r['timezone']}))
 d=s['yesterday'];yesterday='<section id="yesterday">'+section_head('Yesterday',d['date'])+'<div class="yesterday-list">'
 for item in d['items']:
  yesterday+='<article><h3>'+E(item['title'])+'</h3><details><summary>Outcome, unresolved work &amp; sources</summary>'+evidence(item['content'])+'</details></article>'
 parts.append(yesterday+'</div>'+('' if d['items'] else '<p>None</p>')+'<details class="foot-note"><summary>Activity coverage</summary><p>'+E(d['coverage'])+'</p></details></section>')
 parts.append('<p class="footer">'+E(r['footer'])+'</p>')
 css=(ASSETS/'brief.css').read_text();js=(ASSETS/'brief.js').read_text()
 return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+E(r['page_title'])+'</title><style>'+css+'</style></head><body><main>'+''.join(parts)+'</main><script>'+js+'</script></body></html>'
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('snapshot',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
 args.output.write_text(render(json.loads(args.snapshot.read_text())))
 print(args.output)
