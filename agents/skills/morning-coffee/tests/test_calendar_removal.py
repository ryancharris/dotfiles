"""Local event removal frees verified time without dropping overlapping evidence."""
from copy import deepcopy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from calendar_state import calendar_key, load_calendar_state, save_calendar_state, save_calendar_removal, scheduling_snapshot
from day_calendar import calendar_data
from local_history import export_history
from local_plan_server import handler_for, session_snapshot
from plan_day import suggest
from plan_submission import save_plan, PlanError
from render_brief import render, today_rows
from report_history import publish
from test_report_history import snapshot


class CalendarRemovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = snapshot()
        self.event = self.data['agenda']['events'][0]
        self.event.update(start='2026-10-19T10:00:00-04:00', end='2026-10-19T11:00:00-04:00')
        self.data['availability'] = {'status':'complete', 'checked_at':self.data['collected_at'],
            'coverage':'Synthetic primary calendar', 'window_start':'09:00', 'window_end':'17:00',
            'busy':[{key:self.event[key] for key in ('start','end')}]}
        self.key = calendar_key(self.data, self.event)
        self.request = {'key':self.key, 'start':self.event['start'], 'end':self.event['end'], 'removed':True, 'base_removed':False}
        self.token = 'test-removal-' + 'x'*40
        self.server = ThreadingHTTPServer(('127.0.0.1',0), handler_for(self.data,self.root,self.token))
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def post(self, path, request, **headers):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        connection.request('POST',path,json.dumps(request),{'Content-Type':'application/json','Origin':self.origin,'X-Brief-Token':self.token,**headers})
        response=connection.getresponse();result=response.status,json.loads(response.read());connection.close();return result

    def current(self):
        return session_snapshot(self.data,self.root)

    def test_remove_frees_server_validated_plan_and_restore_retains_saved_choice(self):
        request={'date':self.data['report']['date'],'timezone':self.data['report']['timezone'],
                 'blocks':[{'kind':'focus','start':600,'minutes':60}]}
        before=deepcopy(self.data)
        self.assertEqual(self.post('/submit',request)[0],400)
        self.assertEqual(self.post('/calendar/remove',self.request)[0],200)
        current=self.current()
        self.assertEqual(today_rows(current),[])
        self.assertEqual(calendar_data(current)['fixed'],[])
        self.assertEqual(self.post('/submit',request)[0],200)
        self.assertEqual(self.data,before)
        self.assertEqual(self.post('/calendar/remove',dict(self.request,removed=False,base_removed=True))[0],200)
        current=self.current()
        self.assertTrue(calendar_data(current)['submitted_blocks'][0]['conflict'])
        self.assertEqual(len(current['submitted_plan']['blocks']),1)
        self.assertEqual(self.post('/submit',request)[0],400)
        self.assertTrue(any(x.get('action')=='set_removed' for x in export_history(self.root)['events']))

    def test_reload_refresh_reschedule_and_day_scope(self):
        self.assertEqual(self.post('/calendar/remove',self.request)[0],200)
        self.event['title']='Renamed meeting'
        self.assertEqual(today_rows(self.current()),[])
        archived=publish(self.root,self.current(),'morning-coffee')
        stored=json.loads(Path(archived['snapshot']).read_text())
        self.assertEqual(stored['agenda']['events'],self.data['agenda']['events'])
        self.assertEqual(today_rows(stored),[])
        self.assertIn('Restore',render(dict(self.current(),calendar_interaction={'endpoint':self.origin+'/calendar/done','token':self.token})))
        self.event.update(start='2026-10-19T13:00:00-04:00',end='2026-10-19T14:00:00-04:00')
        self.assertEqual(len(today_rows(self.current())),1)
        self.assertEqual(self.post('/calendar/remove',self.request)[0],409)
        other=deepcopy(self.data);other['report']['date']='2026-10-20'
        self.assertEqual(load_calendar_state(self.root,other,include_removed=True)['removed'],{})

    def test_overlap_anonymous_all_day_and_legacy_intervals(self):
        for overlap in [dict(self.event,id='other'),
                        dict(self.event,id='other',start='2026-10-19T10:30:00-04:00',end='2026-10-19T11:30:00-04:00')]:
            with self.subTest(overlap=overlap['start']):
                data=deepcopy(self.data);data['agenda']['events'].append(overlap)
                data['availability']['busy'].append({k:overlap[k] for k in ('start','end')})
                data['availability']['busy'].append({'start':'2026-10-19T15:00:00-04:00','end':'2026-10-19T16:00:00-04:00'})
                data['calendar_removed']={self.key:{k:self.event[k] for k in ('start','end')}}
                fixed=calendar_data(data)['fixed']
                self.assertTrue(any(x['start']==900 and x['anonymous'] for x in fixed))
                self.assertTrue(any(x['label']==overlap['title'] for x in fixed))
                self.assertEqual(len(fixed),2)
        data=deepcopy(self.data);data['agenda']['events'][0].update(start='2026-10-19',end='2026-10-20',all_day=True)
        bounds={k:data['agenda']['events'][0][k] for k in ('start','end')}
        data['availability']['busy']=[dict(bounds,event_id=self.event['id'])];data['calendar_removed']={self.key:bounds}
        self.assertEqual(calendar_data(data)['fixed'],[])
        self.assertEqual(suggest(data)['status'],'suggested')

    def test_completion_is_independent_and_bad_or_stale_requests_cannot_write(self):
        self.assertEqual(self.post('/calendar/remove',self.request,Origin='https://example.com')[0],403)
        self.assertEqual(self.post('/calendar/remove',dict(self.request,key='0'*64))[0],400)
        self.assertEqual(self.post('/calendar/remove',dict(self.request,removed=1))[0],400)
        self.assertEqual(self.post('/calendar/remove',self.request)[0],200)
        self.assertEqual(self.post('/calendar/remove',self.request)[0],409)
        save_calendar_state(self.root,self.data,{'key':self.key,'done':True})
        self.assertEqual(today_rows(self.current()),[])
        self.assertEqual(self.post('/calendar/remove',dict(self.request,removed=False,base_removed=True))[0],200)
        self.assertTrue(self.current()['calendar_state'][self.key])
        self.assertTrue(calendar_data(self.current())['fixed'])
        path=next((self.root/'workspace').glob('calendar-*.json'));path.write_text('{')
        self.assertEqual(self.post('/calendar/remove',self.request)[0],400)
        self.assertEqual(path.read_text(),'{')

if __name__=='__main__':unittest.main()
