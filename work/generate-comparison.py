"""Generate both ADE comparison views and the social card from work/comparison-grades.json."""
import html, json, sys
from pathlib import Path

work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
M = json.loads((work / 'comparison-grades.json').read_text())
R, F, A = M['rubric'], M['fields'], M['apps']
e = html.escape
TIERS = [('entry', 'Entry: what makes it an ADE'), ('hard', 'Hard requirements'), ('extra', 'Extra credit (tie-break only)')]
ORDER = list(A)  # manifest order: ranked recommendations, then other tested apps
WORD = {0: 'none', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight'}
n_apps = len(A); n_picks = len(M['ranking']['personal'])

def grade(g):
    r = R[g]
    return (f'<span class="grade grade-{g}" data-grade="{g}" title="{e(r["meaning"])}">'
            f'<span class="grade-symbol" aria-hidden="true">{r["symbol"]}</span><span>{r["label"]}</span></span>')

def app_cell(name, a):
    ver = f'v{a["tested_version"]}'
    if a.get('current_version'):
        ver += f' tested · {a["current_version"]} current'
    if a['status'] == 'passed':
        flag = '<small class="status pass">Passed both picks</small>'
    else:
        missing = a.get('failed_on', a.get('unverified_on', []))
        gates = ', '.join(F[f]['short'] if f.startswith('entry_') else F[f]['label'].split(' ')[0] for f in missing)
        label = 'Fails' if a['status'] == 'failed' else 'Unverified'
        flag = f'<small class="status fail">{label} {gates}</small>'
    lic=a['license']
    license_link=f'<a class="license-label" data-license-app="{e(name)}" data-license-id="{e(lic["id"])}" href="{e(lic["source_url"])}">{e(lic["label"])}</a>'
    return f'<td><strong>{e(name)}</strong><small class="ver">{e(ver)}</small>{license_link}{flag}</td>'

def table(tier, title):
    fields = [k for k, f in F.items() if f['tier'] == tier]
    head = ''.join(f'<th>{e(F[k]["label"])}</th>' for k in fields)
    rows = []
    for name in ORDER:
        a = A[name]; cells = []
        for k in fields:
            c = a['grades'][k]; extra = ''
            if k == 'x_open_source':
                lic=a['license']
                extra=f'<p class="license-scope">{e(lic["scope_note"])}</p>'
            if k == 'entry_keys':
                extra = f'<p class="route"><b>Route</b> {e(a["keys_route"])}</p>'
            cells.append(f'<td>{grade(c["grade"])}<p>{e(c["note"])}</p>{extra}</td>')
        cls = ' class="row-pass"' if a['status'] == 'passed' else ''
        rows.append(f'<tr data-app="{e(name)}"{cls}>{app_cell(name, a)}{"".join(cells)}</tr>')
    return (f'<section class="compare"><div class="compare-head"><div class="section-label"><span class="index">{ {"entry":"03","hard":"04","extra":"05"}[tier] }</span>'
            f'<h2>{e(title)}</h2></div><p>{e(M["tiers"][tier])}</p></div>'
            f'<p class="scroll-cue">Scroll horizontally to see all columns →</p>'
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="{e(title)}; scroll horizontally for all columns">'
            f'<table class="t-{tier}"><thead><tr><th>Environment</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')

def req_list():
    out = []
    for tier, title in TIERS:
        items = ''.join(f'<li><b>{e(F[k]["label"])}</b> {e(F[k]["description"])}</li>' for k, f in F.items() if f['tier'] == tier)
        out.append(f'<div class="req-tier req-{tier}"><h3>{e(title)}</h3><ul>{items}</ul></div>')
    return ''.join(out)

def picks():
    rk = M['ranking']; lists = []
    for key in ['personal', 'general']:
        p = M['picks'][key]
        items = []
        for i,n in enumerate(rk[key]):
            state = 'Qualified' if A[n]['status'] == 'passed' else 'Provisional'
            items.append(f'<div class="rank" data-app="{e(n)}" data-qualification="{state.lower()}"><div class="number">0{i+1}</div><strong>{e(n.upper())}</strong><span><em class="pick-status">{state}.</em> {e(rk["reasons"][n])}</span></div>')
        lists.append(f'<div class="pick" data-pick="{key}"><p class="pick-head">{e(p["label"])}</p><p class="pick-detail">{e(p["detail"])}</p>{"".join(items)}</div>')
    same = '<p class="caveat"><b>Same top three, same order.</b> Paseo, Sheprd and Agentastic are the ranked recommendations for both audiences. Provisional picks retain the evidence limits shown above.</p>'
    return f'<div class="picks">{"".join(lists)}</div>{same}<p class="caveat"><b>Ranking basis.</b> {e(rk["tie_break"])}</p>'


def legend():
    items = ''.join(f'<div class="grade-key-item">{grade(k)}{e(v["meaning"])}</div>' for k, v in R.items())
    return ('<aside class="grade-key" aria-label="Evidence grading legend"><p><b>How to read the grades.</b> Each cell states its scope. '
            'Grades are never added into a score; one hard miss fails the pick, and extras cannot compensate. Highlighted rows are qualified; provisional recommendations keep their partial grades.</p>'
            f'<div class="grade-key-items">{items}</div></aside>')

def excluded():
    failed = ''.join(f'<li><b>{e(n)} {e(a["tested_version"])}</b> {e(a["summary"])}</li>' for n, a in A.items() if a['status'] != 'passed')
    ex = ''.join(f'<li><b>{e(x["app"])}</b> {e(x["reason"])}</li>' for x in M['excluded'])
    return ('<section class="lists"><div><div class="section-label"><span class="index">06</span><h2>Failed or still unverified</h2></div>'
            f'<ul class="plain">{failed}</ul></div><div><div class="section-label"><span class="index">07</span><h2>Excluded before testing</h2></div>'
            f'<ul class="plain">{ex}</ul></div></section>')

def notable():
    items = ''.join(f'<li>{e(x)}</li>' for x in M['notable_behaviour'])
    meth = ''.join(f'<li>{e(x)}</li>' for x in M['method'])
    return ('<section class="lists"><div class="notable"><div class="section-label"><span class="index">!</span><h2>Notable behaviour</h2></div>'
            f'<ul class="plain">{items}</ul></div><div><div class="section-label"><span class="index">08</span><h2>Method</h2></div><ul class="plain">{meth}</ul></div></section>')

SOURCES = [('Retained hands-on evidence', 'evidence-2026-11-12/README.md'), ('OpenAI ent26 classification (29 July entry)', 'https://learn.chatgpt.com/docs/changelog?date=2026-10-15'), ('Paseo', 'https://paseo.sh/download'), ('Paseo orchestration', 'https://paseo.sh/docs/orchestration-workflows'),
           ('Sheprd', 'https://sheprd.org/'), ('Sheprd config', 'https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/website/docs/configuration.md'),
           ('Agentastic', 'https://agentastic.dev'), ('Agentastic settings', 'https://agentastic.dev/docs/reference/settings'),
           ('Orca', 'https://www.onorca.dev/'), ('Pane', 'https://github.com/greenfield-inc/Pane'),
           ('Ghostex', 'https://github.com/maddada/Ghostex/blob/main/README.md'), ('T3 Code', 'https://t3.codes/'),
           ('OpenChamber', 'https://github.com/openchamber/openchamber'), ('Conductor status', 'https://www.conductor.build/announcement')]


STYLE = r"""
:root{--paper:#f0ecdf;--ink:#171714;--line:#a8a497;--red:#dd3a1d;--yellow:#f2cf4d;--blue:#173d5b;--white:#fbf9f1}
*{box-sizing:border-box}body{margin:0;background:#d4d0c4;color:var(--ink);font-family:Arial,Helvetica,sans-serif}.sheet{width:min(1520px,100%);margin:auto;background:var(--paper);padding:36px 52px 30px}h1,h2,h3,p{margin:0}
.micro{font:700 13px/1.2 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.08em;text-transform:uppercase}.mast{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid var(--ink);padding-bottom:12px}.mast .issue{text-align:right}
.headline{display:grid;grid-template-columns:1fr 340px;gap:34px;align-items:end;padding:34px 0 30px}.headline h1{font-family:Impact,'Arial Narrow',sans-serif;text-transform:uppercase;font-weight:900;font-size:clamp(64px,7vw,108px);letter-spacing:-.025em;line-height:.86}.headline h1 em{font-style:normal;color:var(--red)}
.lede{border-left:5px solid var(--red);padding-left:19px;font:20px/1.28 Georgia,serif}.lede b{display:block;margin-bottom:8px;font:700 12px/1.2 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase}
.top{display:grid;grid-template-columns:1.2fr 1fr;border-top:3px solid var(--ink);border-bottom:3px solid var(--ink)}.requirements{padding:20px 30px 22px 0}
.section-label{display:flex;align-items:center;gap:10px;margin-bottom:15px}.section-label .index{display:grid;place-items:center;width:28px;height:28px;background:var(--ink);color:var(--paper);font:700 14px ui-monospace,monospace}.section-label h2{font:800 16px/1 Arial,sans-serif;text-transform:uppercase;letter-spacing:.08em}
.req-tier{margin-bottom:14px}.req-tier h3{font:700 12px/1.2 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;border-bottom:2px solid var(--ink);padding-bottom:5px;margin-bottom:7px}.req-extra h3{border-bottom-style:dashed;color:#5c584e}
.req-tier ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:6px 22px}.req-tier li{font-size:14px;line-height:1.3}.req-tier li b{display:block;font-size:15px;color:var(--ink)}.req-tier li b:before{content:'↗ ';color:var(--red)}
.brief-tldr{margin-top:6px;font-size:14px;line-height:1.4}.brief-tldr summary{font-weight:700;cursor:pointer}.brief-tldr p{padding-top:8px}
.verdict{background:var(--yellow);padding:20px 25px 20px 28px;border-left:3px solid var(--ink)}.verdict .section-label .index{background:#a02917}
.picks{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pick-head{font:700 13px/1.2 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;border-bottom:2px solid var(--ink);padding-bottom:6px}.pick-detail{font-size:12px;line-height:1.3;padding:6px 0 2px;color:#3b382f}
.rank{display:grid;grid-template-columns:34px 1fr;gap:3px 10px;align-items:baseline;border-bottom:1px solid #9d893f;padding:7px 0}.rank .number{font:700 26px/1 Georgia,serif;color:#a02917}.rank strong{font:900 26px/.95 Impact,'Arial Narrow',sans-serif;letter-spacing:.01em}.pick-status{font-style:normal;font-weight:700}.rank span{grid-column:2;font-size:13px;line-height:1.25}
.verdict .caveat{font-size:14px;line-height:1.35;margin-top:12px}
.compare{padding-top:23px}.compare-head{display:flex;justify-content:space-between;align-items:end;margin-bottom:11px;gap:20px}.compare-head p{font-size:13px;line-height:1.3;max-width:460px;text-align:right}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{text-align:left;vertical-align:top;border-top:1px solid var(--ink);padding:11px 10px 12px 0}th{font:700 12px ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase}td{font-size:14px;line-height:1.25}
th:first-child,td:first-child{width:150px}td:first-child strong{display:block;font-size:19px;letter-spacing:-.03em}td p{margin-top:4px}
table.t-hard{min-width:1300px}table.t-extra{min-width:1000px}table.t-entry{min-width:900px}
.license-label{display:block;font:700 12px/1.35 ui-monospace,monospace;color:var(--blue);margin-top:5px;text-underline-offset:2px}.license-scope{font-size:12px;color:#3b382f}.ver{display:block;margin-top:4px;font:700 11px/1.3 ui-monospace,monospace;color:#5c584e}.status{display:block;margin-top:6px;font:700 10px/1.3 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.05em}.status.pass{color:var(--ink);background:var(--yellow);display:inline-block;padding:2px 5px;border:1px solid var(--ink)}.status.fail{color:#a02917}
tr.row-pass td{background:rgba(242,207,77,.32)}tr.row-pass td:first-child{box-shadow:inset 6px 0 0 var(--red);padding-left:12px}
.route{font-size:12px;color:#3b382f;border-top:1px dashed var(--line);padding-top:4px}.route b{font:700 10px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.05em}
.lists{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:26px;border-top:3px solid var(--ink);padding-top:20px}ul.plain{margin:0;padding:0;list-style:none}ul.plain li{font-size:14px;line-height:1.35;padding:6px 0;border-bottom:1px solid var(--line)}ul.plain li b{margin-right:4px}
.notable .section-label .index{background:var(--red)}
.picker{margin-top:23px;border-top:3px solid var(--ink);padding-top:18px}.picker p{font-size:14px;margin-top:6px}.picker select,.picker button{font:15px Arial,sans-serif;padding:4px 8px;margin:0 10px 6px 4px}
.foot{display:grid;grid-template-columns:1.35fr 1fr;gap:40px;margin-top:22px;font-size:13px;line-height:1.4;border-top:1px solid var(--line);padding-top:14px}.foot b{font:700 11px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em}.foot a{color:var(--blue);text-decoration-thickness:1px;text-underline-offset:2px}
.end{display:flex;justify-content:space-between;border-top:2px solid var(--ink);padding-top:10px;margin-top:18px;color:#55534b}
.scroll-cue{display:none}
.grade{display:flex;align-items:center;gap:6px;margin:0 0 7px;font:700 11px/1.2 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;color:var(--grade-ink)}
.grade-symbol{display:grid;place-items:center;flex:0 0 19px;width:19px;height:19px;border:1.5px solid currentColor;font:800 15px/1 Arial,sans-serif}
.grade-proven{--grade-ink:#171714}.grade-proven .grade-symbol{background:#171714;color:#f0ecdf;border-color:#171714}
.grade-supported{--grade-ink:#173d5b}.grade-supported .grade-symbol{background:var(--white)}
.grade-partial{--grade-ink:#765600}.grade-partial .grade-symbol{background:linear-gradient(90deg,#e5d6a6 50%,var(--white) 50%)}
.grade-gap{--grade-ink:#a02917}.grade-gap .grade-symbol{background:var(--red);border-color:var(--red);color:#fff}
.grade-unknown{--grade-ink:#625e53}.grade-unknown .grade-symbol{border-style:dashed}
.grade-key{margin:15px 0 4px;padding:12px 0 13px;border-top:2px solid var(--ink);border-bottom:1px solid var(--line)}.grade-key>p{font-size:13px;line-height:1.4;margin-bottom:11px}.grade-key-items{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.grade-key-item{font-size:12px;line-height:1.35}.grade-key .grade{margin-bottom:5px}
@media(max-width:500px){.req-tier ul{grid-template-columns:1fr}.mast{gap:12px;flex-wrap:wrap}.picks{grid-template-columns:1fr}}
@media(max-width:800px){.scroll-cue{display:block;font-size:13px;margin-bottom:10px}.sheet{padding:24px 20px}.headline{grid-template-columns:1fr;gap:22px}.headline h1{font-size:clamp(52px,13vw,96px)}.top{grid-template-columns:1fr}.requirements{padding-right:0}.verdict{border-left:0;border-top:3px solid var(--ink)}.compare-head{display:block}.compare-head p{text-align:left;margin-top:6px}.lists{grid-template-columns:1fr;gap:16px}.foot{grid-template-columns:1fr;gap:12px}.end{gap:12px}.grade-key-items{grid-template-columns:repeat(2,1fr);gap:14px}.grade-key-items .grade-key-item:last-child{grid-column:1/-1}}
"""

def page(detailed):
    title = 'Compare agent environments interactively' if detailed else f'{WORD[n_apps].capitalize()} ADEs tested: my top {WORD[n_picks]}'
    t3 = A['T3 Code']
    picker = ''
    script = ''
    if detailed:
        opts = ''.join(f'<option>{e(n)}</option>' for n in ORDER)
        opts2 = ''.join(f'<option>{e(n)}</option>' for n in ORDER[1:] + ORDER[:1])
        picker = (f'<section class="picker"><div class="section-label"><span class="index">↔</span><h2>Choose apps to compare</h2></div>'
                  f'<p>Show any two apps in all three tables.</p><p><label>First app <select id="left">{opts}</select></label> '
                  f'<label>Second app <select id="right">{opts2}</select></label> <button id="all" type="button">Show all {WORD[n_apps]}</button></p></section>')
        script = ("<script>(()=>{const left=document.getElementById('left'),right=document.getElementById('right'),all=document.getElementById('all');"
                  "const rows=[...document.querySelectorAll('tr[data-app]')];function show(){rows.forEach(row=>{row.hidden=![left.value,right.value].includes(row.dataset.app)})}"
                  "left.addEventListener('change',show);right.addEventListener('change',show);all.addEventListener('click',()=>rows.forEach(row=>row.hidden=false));})();</script>")
    srcs = ' · '.join(f'<a href="{u}">{e(t)}</a>' for t, u in SOURCES)
    brief = ('Entry, hard and extra tiers were settled on 12 November 2026 and replace the earlier six-app brief. '
             'Two picks share one grid: my setup (heavy dotfiles, Enterprise accounts) and a fresh setup (minimal dotfiles). '
             'Diff/review was promoted to a hard requirement, and H7 (no config changes without consent) was added after testing showed apps writing into other tools\' configs. '
             'A hosted agent CLI that carries the provider key counts for entry, with the route recorded. Mobile and inline comments are optional and earn no credit.')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<style>{STYLE}</style></head>
<body><main class="sheet">
<div class="mast micro"><span>Field notes / developer tools</span><span>Independent comparison · 12 Nov 2026</span><span class="issue">0{n_apps} tested<br>0{n_picks} ranked picks</span></div>
<header class="headline"><h1>{WORD[n_apps].capitalize()} <em>ADEs</em> tested.<br>My top {WORD[n_picks]}.</h1><p class="lede"><b>The assignment</b>Find a home for parallel coding agents that keeps my shell, my keys and my Enterprise accounts, lets me pick TUI or GUI per session, and leaves other tools' configs alone.</p></header>
<section class="top"><div class="requirements"><div class="section-label"><span class="index">01</span><h2>The requirements</h2></div>{req_list()}<details class="brief-tldr"><summary>How this brief evolved</summary><p>{e(brief)}</p></details></div>
<div class="verdict"><div class="section-label"><span class="index">02</span><h2>The call / two top-3 lists</h2></div>{picks()}</div></section>
{picker}
{legend()}
{table('entry', 'Entry / is it an ADE?')}
{table('hard', 'Hard requirements')}
{table('extra', 'Extra credit')}
{excluded()}
{notable()}
<footer class="foot"><p><b>Limits of the evidence</b><br>Grades cover the tested version of each app on one macOS host on 12 November 2026, in isolated profiles. T3 Code was tested on {e(t3["tested_version"])}; {e(t3["current_version"])} is current and may differ. OpenAI Enterprise rests on the existing ChatGPT login whose plan claim is ent26. Paseo, Sheprd, T3 Code, Pane and OpenChamber opened non-login shells in the recorded routes. Named aliases and exports do not by themselves prove every startup file or input binding. H3 notes identify the missing scope. H7 grades for Sheprd, T3 Code, Agentastic and OpenChamber rest on one run each; other paths (skill-install commands, upgrades) may differ. Linux builds and most free-tier claims come from docs.</p><p><b>Sources / further reading</b><br>{srcs}</p></footer>
<div class="end micro"><span>Portable tools / practical evidence</span><span>End of field notes</span></div>
</main>{script}</body></html>
"""

(work / 'ade-comparison-share.html').write_text(page(False))
(work / 'ade-comparison-detailed.html').write_text(page(True))
print('wrote share + detailed')

# ---- social card (1080x1350) ----
CARD_FIELDS = ['entry_delegation', 'h1_tui_gui', 'h2_no_login', 'h3_terminal_setup', 'h4_enterprise', 'h6_diff', 'h7_consent', 'x_open_source']
CARD_LABEL = {'entry_delegation': 'Delegate', 'h1_tui_gui': 'TUI/GUI<br>choice', 'h2_no_login': 'No<br>login', 'h3_terminal_setup': 'Terminal<br>setup',
              'h4_enterprise': 'Enterprise*', 'h6_diff': 'Diff', 'h7_consent': 'Consent', 'x_open_source': 'Open<br>source'}
card_data = {'fields': CARD_FIELDS, 'label': CARD_LABEL,
             'apps': {n: {'status': a['status'], 'license': {'id':a['license']['id'], 'label':a['license']['short_label']}, 'grades': {f: a['grades'][f]['grade'] for f in CARD_FIELDS}} for n, a in A.items()}}
rk = M['ranking']
card_notes = rk['card_notes']
rows = ''.join(f'<i>{i+1}</i><b>{e(n)}</b><span class="pick-note" data-app="{e(n)}" data-qualification="{"qualified" if A[n]["status"] == "passed" else "provisional"}">{e(card_notes[n])}</span>' for i,n in enumerate(rk['personal']))
if rk['identical']:
    vhead = 'Top 3 · for my setup <em>and</em> for a fresh setup'
    vnote = '<p class="vnote">*Enterprise: required for my setup; extra credit for a fresh setup.</p>'
else:
    raise SystemExit('card layout needs separate lists for different picks')
t3 = A['T3 Code']
card = (work / 'ade-comparison-card.html').read_text()
start = card.index('<main class="card">'); end = card.index('</main>') + len('</main>')
main = f'''<main class="card">
  <div class="kicker"><span>Agent dev environments / hands-on grades</span><span>Nov 2026</span></div>
  <h1>{WORD[n_apps].capitalize()} <em>ADE<span class="lc">s</span></em> tested.<br>My top {WORD[n_picks]}.</h1>
  <section class="verdict" aria-label="Top three recommendations">
    <p class="vhead">{vhead}</p>
    {rows}
    {vnote}
  </section>
  <section class="grid" id="grid" aria-label="Evidence grades, {n_apps} apps by {len(CARD_FIELDS)} decisive fields"></section>
  <section class="legend" id="legend" aria-label="Grade key"></section>
  <footer class="foot">
    <span><strong>Ranked on evidence, not a summed score.</strong> Only fully qualified rows are highlighted. One macOS host, 12 Nov 2026; T3 Code {e(t3["tested_version"])} tested ({e(t3["current_version"])} current). Unknown is not failure. Herdr, cmux, Conductor excluded.</span>
  </footer>
</main>
<script>
const DATA={json.dumps(card_data, ensure_ascii=False)};
const SYM={{proven:'✓',supported:'◇',partial:'◐',gap:'×',unknown:'?'}};
const KEY=[['proven','Proven'],['supported','Docs only'],['partial','Partial'],['gap','Gap'],['unknown','Unknown']];
const nReq=DATA.fields.filter(f=>!f.startsWith('x_')).length,nX=DATA.fields.length-nReq;
const g=document.getElementById('grid');let h=`<div></div><div class="group" style="grid-column:span ${{nReq}}">Requirements</div><div class="group bonus" style="grid-column:span ${{nX}}">Extra</div>`;
h+='<div></div>';for(const f of DATA.fields)h+=`<div class="colhead${{f.startsWith('x_')?' bonus':''}}">${{DATA.label[f]}}</div>`;
for(const [app,row] of Object.entries(DATA.apps)){{const pick=row.status==='passed'?' row-pick':'';h+=`<div class="app${{pick}}" data-app="${{app}}"><span class="app-name">${{app}}</span><span class="app-license" data-license-id="${{row.license.id}}">${{row.license.label}}</span></div>`;
 for(const f of DATA.fields){{const v=row.grades[f];h+=`<div class="cell${{pick}}"><span class="chip ${{v}}" data-app="${{app}}" data-field="${{f}}" data-grade="${{v}}" title="${{v}}">${{SYM[v]}}</span></div>`;}}}}
g.innerHTML=h;
document.getElementById('legend').innerHTML=KEY.map(([k,t])=>`<div><span class="chip ${{k}}">${{SYM[k]}}</span>${{t}}</div>`).join('');
</script>'''
card = card[:start] + main + card[card.index('</body>'):] if '<script>' not in card[end:card.index('</body>')] else card[:start] + main + '\n' + card[card.index('</body>'):]
(work / 'ade-comparison-card.html').write_text(card)
print('wrote card')
