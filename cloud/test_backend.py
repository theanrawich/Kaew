import json
import os
import tempfile
import threading
import unittest
import subprocess
import sys
import time
import socket
import sqlite3
from contextlib import closing
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
from server import create_server, migrate
from outbox import Outbox
from outbox_worker import OutboxWorker
from voice_pipeline import VoicePipeline


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, 'kaew.sqlite3')
        self.server = create_server('127.0.0.1', 0, self.path, 'device-secret', 'admin-secret')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:%s' % self.server.server_port
        self.sample = {'device_id': 'node-1', 'session': 7, 'seq': 1,
                       'level': 'wet', 'temperature_c': 25.0, 'tds_adc': 1234}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, method, path, token=None, data=None):
        headers = {'Content-Type': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + token
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=3) as res:
                return res.status, json.load(res)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_auth_validation_idempotency_and_persistence(self):
        self.assertEqual(self.request('POST', '/api/telemetry', data=self.sample)[0], 401)
        self.assertEqual(self.request('POST', '/api/telemetry', 'admin-secret', self.sample)[0], 401)
        self.assertEqual(self.request('POST', '/api/telemetry', 'device-secret', self.sample)[0], 201)
        self.assertEqual(self.request('POST', '/api/telemetry', 'device-secret', self.sample)[0], 200)
        conflict = dict(self.sample, level='dry')
        self.assertEqual(self.request('POST', '/api/telemetry', 'device-secret', conflict)[0], 409)
        self.assertEqual(self.request('POST', '/api/telemetry', 'device-secret', dict(self.sample, seq=2, level='50%'))[0], 400)
        self.assertEqual(self.request('GET', '/api/telemetry', 'device-secret')[0], 401)
        status, result = self.request('GET', '/api/telemetry', 'admin-secret')
        self.assertEqual(status, 200)
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['level'], 'wet')
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.server = create_server('127.0.0.1', 0, self.path, 'device-secret', 'admin-secret')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:%s' % self.server.server_port
        self.assertEqual(len(self.request('GET', '/api/telemetry', 'admin-secret')[1]['items']), 1)

    def test_device_identity_cannot_be_spoofed(self):
        self.assertEqual(self.request('POST', '/api/telemetry', 'device-secret', dict(self.sample, device_id='other'))[0], 403)

    def test_status_reports_persisted_observation(self):
        self.request('POST', '/api/telemetry', 'device-secret', self.sample)
        status, body = self.request('GET', '/api/status', 'admin-secret')
        self.assertEqual(status, 200)
        self.assertEqual(body['device']['id'], 'node-1')
        self.assertTrue(body['device']['online'])

    def test_concurrent_retries_are_idempotent(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.request('POST', '/api/telemetry', 'device-secret', self.sample)[0], range(8)))
        self.assertEqual(results.count(201), 1)
        self.assertEqual(results.count(200), 7)

    def test_simulator_to_database_pipeline(self):
        env = dict(os.environ, KAEW_CLOUD_URL=self.url, KAEW_DEVICE_TOKEN='device-secret',
                   KAEW_OUTBOX_PATH=os.path.join(self.directory.name, 'sender.sqlite3'), KAEW_PYTHON=sys.executable)
        result = subprocess.run(['node', os.path.join(os.path.dirname(__file__), 'simulate.mjs')],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        status, body = self.request('GET', '/api/telemetry', 'admin-secret')
        self.assertEqual(status, 200)
        self.assertEqual(body['items'][0]['level'], 'wet')
        self.assertEqual(body['items'][0]['tds_adc'], 1234)
        self.assertEqual(body['items'][0]['source'], 'simulated')

    def test_dashboard_is_served(self):
        with urllib.request.urlopen(self.url + '/', timeout=3) as res:
            self.assertEqual(res.status, 200)
            self.assertIn(b'Kaew telemetry', res.read())

    def test_offline_outbox_survives_restart_and_flushes(self):
        path = os.path.join(self.directory.name, 'outbox.sqlite3')
        outbox = Outbox(path)
        self.assertTrue(outbox.enqueue(self.sample))
        self.assertFalse(outbox.enqueue(self.sample))
        self.assertEqual(outbox.flush('http://127.0.0.1:1', 'device-secret'), 0)
        self.assertEqual(Outbox(path).count(), 1)
        self.assertEqual(Outbox(path).flush(self.url, 'device-secret'), 1)
        self.assertEqual(Outbox(path).count(), 0)
        self.assertEqual(len(self.request('GET', '/api/telemetry', 'admin-secret')[1]['items']), 1)

    def test_outbox_bounds_conflicts_and_transport_security(self):
        outbox = Outbox(os.path.join(self.directory.name, 'bounded.sqlite3'), capacity=1)
        outbox.enqueue(self.sample)
        with self.assertRaises(ValueError): outbox.enqueue(dict(self.sample, level='dry'))
        with self.assertRaises(OverflowError): outbox.enqueue(dict(self.sample, seq=2))
        with self.assertRaises(ValueError): outbox.flush('http://example.com', 'device-secret')
        self.assertEqual(outbox.count(), 1)

    def test_worker_recovers_persisted_queue_automatically(self):
        path = os.path.join(self.directory.name, 'worker.sqlite3')
        Outbox(path).enqueue(self.sample)
        worker = OutboxWorker(Outbox(path), self.url, 'device-secret', idle_seconds=0.05)
        worker.start()
        try:
            deadline = time.monotonic() + 3
            while Outbox(path).count() and time.monotonic() < deadline: time.sleep(0.02)
            self.assertEqual(Outbox(path).count(), 0)
            self.assertEqual(len(self.request('GET', '/api/telemetry', 'admin-secret')[1]['items']), 1)
        finally: worker.stop()

    def test_drinking_event_and_reminder_are_persisted(self):
        drink = {'event_id':'drink-1','kind':'drink','source':'simulated','volume_ml':120}
        self.assertEqual(self.request('POST','/api/events','admin-secret',drink)[0],201)
        self.assertEqual(self.request('POST','/api/events','admin-secret',drink)[0],200)
        self.assertEqual(self.request('POST','/api/events','device-secret',drink)[0],401)
        self.assertEqual(self.request('GET','/api/summary','admin-secret')[1]['drinking_ml'],120)
        reminder = {'interval_minutes':30,'next_due':time.time()-1}
        self.assertEqual(self.request('POST','/api/reminder','admin-secret',reminder)[0],200)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            _, records=self.request('GET','/api/notifications','admin-secret')
            if records['items']: break
            time.sleep(.05)
        self.assertEqual(len(records['items']),1)
        self.assertEqual(records['items'][0]['provider'],'mock')

    def test_existing_database_migrates_without_losing_telemetry(self):
        path=os.path.join(self.directory.name,'old.sqlite3')
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript((Path(__file__).parent/'migrations/001_initial.sql').read_text())
            db.execute("INSERT INTO devices(id) VALUES ('node-1')")
            db.execute("INSERT INTO telemetry(device_id,session,seq,level,temperature_c,tds_adc,received_at) VALUES ('node-1',1,1,'wet',25,1000,1)")
        migrate(path)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],6)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM telemetry').fetchone()[0],1)

    def test_legacy_mock_notification_history_remains_visible(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO notifications(reminder_due,provider,created_at) VALUES (?,?,?)",(100,'mock',100))
        items=self.request('GET','/api/notifications','admin-secret')[1]['items']
        self.assertEqual(items[0]['status'],'legacy_mock')

    def test_worker_reconnects_after_outage(self):
        sock=socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close()
        outbox=Outbox(os.path.join(self.directory.name,'offline.sqlite3')); outbox.enqueue(self.sample)
        worker=OutboxWorker(outbox, 'http://127.0.0.1:%d'%port, 'device-secret', idle_seconds=.05, max_backoff=.2)
        worker.start(); server=None; thread=None
        try:
            deadline=time.monotonic()+3
            while worker.failures==0 and time.monotonic()<deadline: time.sleep(.02)
            self.assertGreater(worker.failures,0); self.assertEqual(outbox.count(),1)
            server=create_server('127.0.0.1',port,os.path.join(self.directory.name,'recovered.sqlite3'),'device-secret','admin-secret')
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            deadline=time.monotonic()+4
            while outbox.count() and time.monotonic()<deadline: time.sleep(.02)
            self.assertEqual(outbox.count(),0)
        finally:
            worker.stop()
            if server: server.shutdown(); server.server_close(); thread.join()

    def test_hydration_goal_is_user_configured_and_persistent(self):
        self.assertEqual(self.request('GET','/api/goal','admin-secret')[1]['goal_ml'],None)
        self.assertEqual(self.request('POST','/api/goal','admin-secret',{'goal_ml':2000})[0],200)
        self.assertEqual(self.request('POST','/api/goal','admin-secret',{'goal_ml':-10})[0],400)
        self.assertEqual(self.request('GET','/api/goal','admin-secret')[1]['goal_ml'],2000)

    def test_low_water_and_fault_notifications_are_deduplicated(self):
        dry = dict(self.sample,level='dry')
        self.assertEqual(self.request('POST','/api/telemetry','device-secret',dry)[0],201)
        self.assertEqual(self.request('POST','/api/telemetry','device-secret',dry)[0],200)
        self.request('POST','/api/telemetry','device-secret',dict(self.sample,seq=2,level='wet'))
        self.request('POST','/api/telemetry','device-secret',dict(self.sample,seq=3,level='dry'))
        fault={'event_id':'f1','kind':'fault','source':'simulated','volume_ml':None}
        self.assertEqual(self.request('POST','/api/events','admin-secret',fault)[0],201)
        self.assertEqual(self.request('POST','/api/events','admin-secret',fault)[0],200)
        records=self.request('GET','/api/notifications','admin-secret')[1]['items']
        self.assertEqual(sorted(x['kind'] for x in records),['fault','low_water'])

    def test_notification_worker_retries_provider_failure(self):
        class Flaky:
            calls=0
            def send(self, text):
                self.calls+=1
                if self.calls==1: raise RuntimeError('network')
                return 'ok'
        provider=Flaky(); self.server.provider=provider
        self.request('POST','/api/events','admin-secret',{'event_id':'retry','kind':'fault','source':'simulated','volume_ml':None})
        deadline=time.monotonic()+7
        while time.monotonic()<deadline:
            items=self.request('GET','/api/notifications','admin-secret')[1]['items']
            if items and items[0]['status']=='delivered': break
            time.sleep(.05)
        self.assertEqual(items[0]['status'],'delivered')
        self.assertEqual(items[0]['attempts'],2)

    def test_simulated_uart_to_notification_worker(self):
        env=dict(os.environ,KAEW_CLOUD_URL=self.url,KAEW_DEVICE_TOKEN='device-secret',KAEW_SIM_LEVEL='dry',
                 KAEW_OUTBOX_PATH=os.path.join(self.directory.name,'acceptance.sqlite3'),KAEW_PYTHON=sys.executable)
        run=subprocess.run(['node',os.path.join(os.path.dirname(__file__),'simulate.mjs')],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            jobs=self.request('GET','/api/notifications','admin-secret')[1]['items']
            if jobs and jobs[0]['status']=='delivered': break
            time.sleep(.05)
        self.assertEqual(jobs[0]['kind'],'low_water')
        self.assertIn('ข้อมูลจำลอง',jobs[0]['text'])
        self.assertEqual(jobs[0]['provider'],'mock')
        self.assertEqual(jobs[0]['status'],'delivered')
        self.assertEqual(self.request('GET','/api/telemetry','admin-secret')[1]['items'][0]['level'],'dry')

    def test_thai_voice_text_intents_use_real_services_and_refill_stays_blocked(self):
        self.assertEqual(self.request('POST','/api/voice','device-secret',{'text':'แก้ว เติมน้ำให้หน่อย'})[0],401)
        status, answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว เติมน้ำให้หน่อย'})
        self.assertEqual(status,200); self.assertEqual(answer['intent'],'refill'); self.assertFalse(answer['executed'])
        status, answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว อีก 30 นาทีเตือนให้ดื่มน้ำ'})
        self.assertEqual(answer['intent'],'reminder'); self.assertEqual(answer['minutes'],30)
        self.assertEqual(self.request('GET','/api/reminder','admin-secret')[1]['reminder']['interval_minutes'],30)
        _, answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว ตอนนี้น้ำเหลือเท่าไหร่'})
        self.assertEqual(answer['level'],'unknown')
        self.request('POST','/api/telemetry','device-secret',self.sample)
        _, answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว น้ำในขวดเป็นอย่างไร'})
        self.assertEqual(answer['level'],'wet'); self.assertNotIn('มิลลิลิตร',answer['reply'])

    def test_voice_reminder_is_one_shot_and_missing_wake_is_ignored(self):
        _,answer=self.request('POST','/api/voice','admin-secret',{'text':'เตือนอีก 5 นาที'})
        self.assertFalse(answer['executed'])
        _,answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว remind อีก ๕ นาที'})
        self.assertEqual(answer['minutes'],5)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE reminders SET next_due=? WHERE id=1',(time.time()-1,))
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            if self.request('GET','/api/reminder','admin-secret')[1]['reminder'] is None: break
            time.sleep(.05)
        self.assertIsNone(self.request('GET','/api/reminder','admin-secret')[1]['reminder'])

    def test_connection_loss_enqueues_only_one_alert(self):
        self.request('POST','/api/telemetry','device-secret',self.sample)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE devices SET last_seen=? WHERE id=?',(time.time()-60,'node-1'))
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            jobs=self.request('GET','/api/notifications','admin-secret')[1]['items']
            if any(j['kind']=='offline' for j in jobs): break
            time.sleep(.05)
        time.sleep(.3)
        jobs=self.request('GET','/api/notifications','admin-secret')[1]['items']
        self.assertEqual(sum(j['kind']=='offline' for j in jobs),1)

    def test_mock_speech_pipeline_invokes_backend_safely(self):
        class FakeASR:
            def transcribe(self, audio): return {'sample1':'แก้ว อีก 30 นาทีเตือนให้ดื่มน้ำ','sample2':'แก้ว เติมน้ำให้หน่อย'}[audio]
        class FakeTTS:
            def synthesize(self, text): return 'mock-audio:'+text
        service=lambda text: self.request('POST','/api/voice','admin-secret',{'text':text})[1]
        voice=VoicePipeline(FakeASR(),service,FakeTTS())
        reminder=voice.handle('sample1'); self.assertTrue(reminder['executed']); self.assertEqual(reminder['minutes'],30)
        refill=voice.handle('sample2'); self.assertFalse(refill['executed']); self.assertTrue(refill['audio'].startswith('mock-audio:'))


if __name__ == '__main__':
    unittest.main()
