import http.client
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from kaew.audio_service import AudioError, TyphoonASR, TYPHOON_ASR_MODEL
import time
import sqlite3
from contextlib import closing
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
from kaew.server import create_server, migrate
from kaew.audio_service import process_audio
from tests.test_audio import wav_fixture


class BackendTest(unittest.TestCase):
    def stt_request(self,token='admin-secret',body=None,content_type='audio/wav',path='/api/stt'):
        headers={'Content-Type':content_type}
        if token: headers['Authorization']='Bearer '+token
        req=urllib.request.Request(self.url+path,data=wav_fixture() if body is None else body,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=3) as res: return res.status,json.load(res)
        except urllib.error.HTTPError as e: return e.code,json.load(e)

    def test_stt_auth_limits_and_unavailable(self):
        with patch.dict(os.environ,{'TYPHOON_API_KEY':''}):
            for token in (None,'device-secret'):
                self.assertEqual(self.stt_request(token)[0],401)
            self.assertEqual(self.stt_request(),(503,{'error':'stt_unavailable'}))
            self.assertEqual(self.stt_request(content_type='application/json')[0],400)
            # Send only headers: the server rejects oversized uploads before reading.
            connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
            try:
                connection.putrequest('POST','/api/stt')
                connection.putheader('Authorization','Bearer admin-secret')
                connection.putheader('Content-Type','audio/wav')
                connection.putheader('Content-Length','2000001')
                connection.endheaders()
                response=connection.getresponse()
                self.assertEqual(response.status,413)
                self.assertEqual(json.load(response),{'error':'audio_too_large'})
            finally: connection.close()

    def test_stt_success_failure_and_shared_command(self):
        asr=TyphoonASR('test-placeholder',transport=lambda *a:json.dumps({'text':'แก้ว เติมน้ำให้หน่อย'}).encode())
        with patch.dict(os.environ,{'TYPHOON_API_KEY':'test-placeholder'}), patch('kaew.server.TyphoonASR',return_value=asr):
            code,result=self.stt_request(path='/api/stt?command=1')
            self.assertEqual(code,200)
            self.assertEqual(result['model'],TYPHOON_ASR_MODEL)
            self.assertEqual(result['command'],self.request('POST','/api/voice','admin-secret',{'text':result['text']})[1])
            self.assertEqual(self.stt_request(body=wav_fixture(True)),(422,{'error':'stt_failed'}))

    def test_stt_recent_admin_only(self):
        self.assertEqual(self.request('GET','/api/stt/recent','admin-secret'),(200,{'items':[]}))
        for token in (None,'device-secret'):
            self.assertEqual(self.request('GET','/api/stt/recent',token)[0],401)

    def test_stt_recent_records_typhoon_attempts(self):
        audio = wav_fixture()
        transcript = {'text': 'เติมน้ำให้หน่อย', 'model': TYPHOON_ASR_MODEL}
        with patch.dict(os.environ, {'TYPHOON_API_KEY': 'typhoon-fixture'}), \
                patch('kaew.server.TyphoonASR') as typhoon:
            typhoon.return_value.transcribe.return_value = transcript['text']
            self.assertEqual(self.stt_request(body=audio), (200, transcript))
            typhoon.assert_called_once_with('typhoon-fixture')
            typhoon.return_value.transcribe.assert_called_once_with(audio)

            typhoon.return_value.transcribe.side_effect = AudioError('fixture failure')
            self.assertEqual(self.stt_request(body=audio, path='/api/stt?command=1'),
                             (422, {'error': 'stt_failed'}))
            self.assertEqual(self.stt_request(body=wav_fixture(True))[0], 422)
            self.assertEqual(typhoon.return_value.transcribe.call_count, 2)

        failed, success = self.request('GET', '/api/stt/recent', 'admin-secret')[1]['items']
        self.assertEqual(failed['error'], 'stt_failed')
        self.assertEqual(failed['model'], TYPHOON_ASR_MODEL)
        for key, value in transcript.items():
            self.assertEqual(success[key], value)
        for item in (failed, success):
            self.assertGreaterEqual(item['elapsed_ms'], 0)

    def test_stt_recent_newest_first_and_cap(self):
        asr=TyphoonASR('test-placeholder',transport=lambda *a:json.dumps({'text':'ESP32 transcript'}).encode())
        before=time.time()
        with patch.dict(os.environ,{'TYPHOON_API_KEY':'test-placeholder'}), patch('kaew.server.TyphoonASR',return_value=asr):
            for index in range(52):
                with patch.object(asr,'transcribe',return_value='transcript %d'%index):
                    self.assertEqual(self.stt_request()[0],200)
            self.assertEqual(self.stt_request(body=wav_fixture(True))[0],422)
        status,result=self.request('GET','/api/stt/recent','admin-secret')
        self.assertEqual(status,200)
        self.assertEqual(len(result['items']),50)
        self.assertEqual([item['text'] for item in result['items']],['transcript %d'%i for i in range(51,1,-1)])
        for item in result['items']:
            self.assertEqual(set(item),{'text','model','at','elapsed_ms'})
            self.assertEqual(item['model'],TYPHOON_ASR_MODEL)
            self.assertLessEqual(before,item['at'])
            self.assertLessEqual(item['at'],time.time())

    def test_stt_page_is_display_only(self):
        with urllib.request.urlopen(self.url+'/stt',timeout=3) as response:
            page=response.read().decode()
            self.assertIn("connect-src 'self'",response.headers['Content-Security-Policy'])
        for forbidden in ('getUserMedia','SpeechRecognition','MediaRecorder','AudioContext'):
            self.assertNotIn(forbidden,page)
        self.assertIn('Kaew – ESP32 mic transcripts',page)
        self.assertIn('/api/stt/recent',page)
        self.assertIn('Asia/Bangkok',page)

    def test_unknown_adc_is_persisted_without_becoming_a_measurement(self):
        sample=dict(self.sample,tds_adc=65535)
        self.assertEqual(self.request('POST','/api/telemetry','device-secret',sample)[0],201)
        self.assertEqual(self.request('GET','/api/telemetry','admin-secret')[1]['items'][0]['tds_adc'],65535)
        self.assertEqual(self.request('POST','/api/telemetry','device-secret',dict(sample,seq=2,tds_adc=4096))[0],400)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, 'kaew.sqlite3')
        self.server = create_server('127.0.0.1', 0, self.path, 'device-secret', 'admin-secret', hydration_provider=None)
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
        self.server = create_server('127.0.0.1', 0, self.path, 'device-secret', 'admin-secret', hydration_provider=None)
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

    def test_voice_level_does_not_present_stale_observation_as_current(self):
        self.request('POST','/api/telemetry','device-secret',self.sample)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE telemetry SET received_at=?',(time.time()-3600,))
        status,body=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว ตอนนี้น้ำเหลือเท่าไหร่'})
        self.assertEqual(status,200)
        self.assertEqual(body['level'],'unknown')

    def test_concurrent_retries_are_idempotent(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.request('POST', '/api/telemetry', 'device-secret', self.sample)[0], range(8)))
        self.assertEqual(results.count(201), 1)
        self.assertEqual(results.count(200), 7)

    def test_dashboard_is_served(self):
        with urllib.request.urlopen(self.url + '/', timeout=3) as res:
            self.assertEqual(res.status, 200)
            self.assertIn(b'Kaew telemetry', res.read())

    def test_events_since_includes_drinks_outside_latest_100(self):
        older = time.time() - 6 * 86400 + .25
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO events VALUES (?,?,?,?,?)', ('older-drink', 'drink', 'measured', 777, older))
            db.execute('INSERT INTO events VALUES (?,?,?,?,?)', ('outside-window', 'drink', 'measured', 999, older - 1))
            db.executemany('INSERT INTO events VALUES (?,?,?,?,?)',
                           [('recent-%d' % i, 'fault', 'simulated', None, older + i + 1) for i in range(125)])
        status, body = self.request('GET', '/api/events', 'admin-secret')
        self.assertEqual(status, 200)
        self.assertEqual(len(body['items']), 100)
        self.assertNotIn('older-drink', [e['id'] for e in body['items']])
        path = '/api/events?since=%s' % older
        status, body = self.request('GET', path, 'admin-secret')
        self.assertEqual(status, 200)
        self.assertEqual(len(body['items']), 126)
        self.assertEqual(body['items'][-1]['id'], 'older-drink')
        self.assertEqual(body['items'][-1]['volume_ml'], 777)
        self.assertEqual(self.request('GET', path)[0], 401)
        self.assertEqual(self.request('GET', path, 'device-secret')[0], 401)

    def test_events_queries_are_validated_and_bounded(self):
        for query in ('since=nope', 'since=nan', 'since=inf', 'since=-1', 'since=1e100', 'since=',
                      'limit=0', 'limit=-1', 'limit=1.5', 'limit=nope', 'limit=inf', 'limit=',
                      'since=1&since=2', 'limit=1&limit=2'):
            with self.subTest(query=query):
                status, body = self.request('GET', '/api/events?' + query, 'admin-secret')
                self.assertEqual(status, 400)
                self.assertIn('error', body)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany('INSERT INTO events VALUES (?,?,?,?,?)',
                           [('bounded-%d' % i, 'drink', 'measured', 10, i + 1) for i in range(2005)])
        for query in ('since=0', 'limit=999999', 'since=0&limit=2001'):
            status, body = self.request('GET', '/api/events?' + query, 'admin-secret')
            self.assertEqual(status, 200)
            self.assertEqual(len(body['items']), 2000)
            self.assertEqual(body['items'][0]['received_at'], 2005)
        self.assertEqual(len(self.request('GET', '/api/events?limit=3', 'admin-secret')[1]['items']), 3)

    def test_existing_database_migrates_without_losing_telemetry(self):
        path=os.path.join(self.directory.name,'old.sqlite3')
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript((Path(__file__).resolve().parents[1]/'migrations/001_initial.sql').read_text())
            db.execute("INSERT INTO devices(id) VALUES ('node-1')")
            db.execute("INSERT INTO telemetry(device_id,session,seq,level,temperature_c,tds_adc,received_at) VALUES ('node-1',1,1,'wet',25,1000,1)")
        migrate(path)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],8)
            self.assertTrue({'model','fallback'} <= {r[1] for r in db.execute('PRAGMA table_info(advice_log)')})
            self.assertEqual(db.execute('SELECT COUNT(*) FROM telemetry').fetchone()[0],1)

    def test_legacy_mock_notification_history_remains_visible(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO notifications(reminder_due,provider,created_at) VALUES (?,?,?)",(100,'mock',100))
        items=self.request('GET','/api/notifications','admin-secret')[1]['items']
        self.assertEqual(items[0]['status'],'legacy_mock')

    def test_profile_validates_persists_and_derives_goal(self):
        def request(method, body=None, token='admin-secret'):
            return self.request(method,'/api/profile',token,body)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO settings VALUES ('goal_ml',2000)")
        self.assertEqual(request('GET')[1],{'body_weight_kg':None,'goal_ml':None})
        self.assertEqual(request('POST',{'body_weight_kg':70},'device-secret')[0],401)
        self.assertEqual(request('GET',token='device-secret')[0],401)
        for body in ({}, {'body_weight_kg':70,'goal_ml':2500}, *(
            {'body_weight_kg':v} for v in (19.99,250.01,True,None,'70',10**400)
        )):
            with self.subTest(body=body):
                self.assertEqual(request('POST',body)[0],400)
        for weight,goal in ((20,1000),(70.5,2327),(250,4000)):
            expected={'body_weight_kg':weight,'goal_ml':goal}
            self.assertEqual(request('POST',{'body_weight_kg':weight}),(200,expected))
            self.assertEqual(request('GET'),(200,expected))
            self.assertEqual(self.request('GET','/api/goal','admin-secret'),(200,{'goal_ml':goal}))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT value FROM settings WHERE key='body_weight_g'").fetchone()[0],250000)
        for path in ('goal','reminder','advice'):
            self.assertEqual(self.request('POST','/api/'+path,'admin-secret',{})[0],404)

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

    def test_simulated_telemetry_to_notification_worker(self):
        sample = dict(self.sample, source='simulated', level='dry')
        self.assertEqual(self.request('POST', '/api/telemetry', 'device-secret', sample)[0], 201)
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
        self.assertEqual(answer['intent'],'reminder'); self.assertFalse(answer['executed'])
        _, answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว ตอนนี้น้ำเหลือเท่าไหร่'})
        self.assertEqual(answer['level'],'unknown')
        self.request('POST','/api/telemetry','device-secret',self.sample)
        _, answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว น้ำในขวดเป็นอย่างไร'})
        self.assertEqual(answer['level'],'wet'); self.assertNotIn('มิลลิลิตร',answer['reply'])

    def test_voice_cannot_create_or_change_reminder(self):
        def reminder():
            return self.request('GET','/api/reminder','admin-secret')[1]['reminder']
        self.assertIsNone(reminder())
        for text in ('เตือนอีก 5 นาที','แก้ว remind อีก ๕ นาที','แก้ว เตือนให้ดื่มน้ำ'):
            status,answer=self.request('POST','/api/voice','admin-secret',{'text':text})
            self.assertEqual(status,200)
            self.assertFalse(answer['executed'])
            if text.startswith('แก้ว'):
                self.assertEqual(answer['intent'],'reminder')
                self.assertIn('อัตโนมัติ',answer['reply'])
        self.assertIsNone(reminder())
        self.request('POST','/api/profile','admin-secret',{'body_weight_kg':70})
        previous=reminder()
        self.assertIsNotNone(previous)
        self.request('POST','/api/voice','admin-secret',{'text':'แก้ว อีก 30 นาทีเตือนให้ดื่มน้ำ'})
        self.assertEqual(reminder(),previous)

    def kinds(self):
        return sorted(x['kind'] for x in self.request('GET','/api/notifications','admin-secret')[1]['items'])

    def test_recovery_alert_after_offline(self):
        self.request('POST','/api/telemetry','device-secret',self.sample)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE devices SET last_seen=? WHERE id=?',(time.time()-60,'node-1'))
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and 'offline' not in self.kinds(): time.sleep(.05)
        self.request('POST','/api/telemetry','device-secret',dict(self.sample,seq=2))
        self.assertIn('recovery',self.kinds())
        self.request('POST','/api/telemetry','device-secret',dict(self.sample,seq=3))
        self.assertEqual(self.kinds().count('recovery'),1)

    def test_out_of_range_temperature_alerts_once_per_episode(self):
        post=lambda seq,t:self.request('POST','/api/telemetry','device-secret',dict(self.sample,seq=seq,temperature_c=t))
        post(1,25.0); self.assertNotIn('sensor_range',self.kinds())
        post(2,60.0); post(3,61.0)
        self.assertEqual(self.kinds().count('sensor_range'),1)
        post(4,25.0)  # back to normal re-arms the alert (cooldown still applies)
        self.assertEqual(self.kinds().count('sensor_range'),1)

    def test_sensor_error_alert(self):
        self.request('POST','/api/telemetry','device-secret',dict(self.sample,tds_adc=65535))
        self.assertIn('sensor_error',self.kinds())

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

    def test_wav_input_to_backend_to_playable_wav_with_mock_speech(self):
        class ASR:
            def transcribe(self,audio): return 'แก้ว อีก 30 นาทีเตือนให้ดื่มน้ำ'
        class TTS:
            def synthesize(self,text): return wav_fixture()
        command=lambda text: self.request('POST','/api/voice','admin-secret',{'text':text})[1]
        out=Path(self.directory.name)/'response.wav'
        result=process_audio(wav_fixture(),ASR(),command,TTS(),out)
        self.assertFalse(result['executed']); self.assertEqual(result['intent'],'reminder')
        self.assertTrue(out.read_bytes().startswith(b'RIFF'))
        self.assertIsNone(self.request('GET','/api/reminder','admin-secret')[1]['reminder'])

    def test_three_voice_examples_with_mock_asr_tts_and_real_backend(self):
        class ASR:
            def __init__(self,text): self.text=text
            def transcribe(self,audio): return self.text
        class TTS:
            def synthesize(self,text): return wav_fixture()
        cases=[('แก้ว เติมน้ำให้หน่อย','refill'),('แก้ว อีก 30 นาทีเตือนให้ดื่มน้ำ','reminder'),('แก้ว ตอนนี้น้ำเหลือเท่าไหร่','level')]
        for index,(text,intent) in enumerate(cases):
            result=process_audio(wav_fixture(),ASR(text),lambda s:self.request('POST','/api/voice','admin-secret',{'text':s})[1],TTS(),Path(self.directory.name)/('reply%d.wav'%index))
            self.assertEqual(result['intent'],intent); self.assertTrue(result['audio_written'])
            if intent=='refill': self.assertFalse(result['executed'])

    def test_advice_uses_history_and_never_authorizes_actuation(self):
        self.request('POST','/api/profile','admin-secret',{'body_weight_kg':70})
        self.request('POST','/api/telemetry','device-secret',dict(self.sample,temperature_c=28,source='device'))
        contexts=[]
        def fake(context):
            contexts.append(context)
            return {'suggested_ml':180,'next_reminder_minutes':45,'reason':'Based on recent intake.'}
        self.server.hydration_provider=fake
        self.request('POST','/api/events','admin-secret',{'event_id':'a1','kind':'drink','source':'simulated','volume_ml':120})
        status,result=self.request('GET','/api/advice','admin-secret')
        self.assertEqual(status,200); self.assertEqual(contexts[0]['drank_ml'],120)
        self.assertEqual(contexts[0]['body_weight_kg'],70)
        self.assertEqual(contexts[0]['goal_ml'],2310)
        self.assertEqual(contexts[0]['temperature_c'],28)
        self.assertEqual(contexts[0]['tank_level'],'wet')
        self.assertEqual(contexts[0]['timezone'],'Asia/Bangkok')
        self.assertLess(contexts[0]['minutes_since_drink'],1)
        self.assertFalse(result['advice']['fallback']); self.assertFalse(result['actuation_allowed'])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM advice_log').fetchone()[0],2)

    def test_advice_schedules_model_and_fallback_and_latest_is_admin_only(self):
        self.assertEqual(self.request('GET','/api/advice','device-secret')[0],401)
        self.assertIsNone(self.request('GET','/api/advice','admin-secret')[1]['advice'])
        def timeout(c): raise TimeoutError()
        for provider,minutes,fallback in ((lambda c:{'next_reminder_minutes':35,'suggested_ml':220,'reason':'Recent intake.'},35,False),(None,60,True),(lambda c:'invalid JSON',60,True),(timeout,60,True)):
            self.server.hydration_provider=provider
            before=time.time()
            self.assertEqual(self.request('POST','/api/profile','admin-secret',{'body_weight_kg':70})[0],200)
            decision=self.request('GET','/api/advice','admin-secret')[1]['advice']
            self.assertEqual(decision['fallback'],fallback); self.assertFalse(decision['actuation_allowed'])
            rem=self.request('GET','/api/reminder','admin-secret')[1]['reminder']
            self.assertEqual(rem['interval_minutes'],minutes)
            self.assertGreaterEqual(rem['next_due'],before+minutes*60)
            self.assertLessEqual(rem['next_due'],time.time()+minutes*60)
        self.assertEqual(self.request('GET','/api/notifications','admin-secret')[1]['items'],[])

    def test_device_drink_reschedules_once_and_is_scoped_to_gateway(self):
        contexts=[]
        def model(c):
            contexts.append(c)
            return {'next_reminder_minutes':25,'suggested_ml':210,'reason':'Recent drink.'}
        self.server.hydration_provider=model
        drink={'event_id':'gateway-1:12345678:9abcdef0:00000001','kind':'drink','source':'measured','volume_ml':150}
        def post(event, token='device-secret'):
            return self.request('POST','/api/events',token,event)[0]
        self.assertEqual(post(drink,'admin-secret'),403)
        self.assertEqual(post(drink,'wrong-token'),401)
        self.assertEqual(post(dict(drink,event_id='node-2:12345678:9abcdef0:00000001')),403)
        self.assertEqual(post(dict(drink,device_id='node-2')),400)
        self.assertEqual(post(dict(drink,source='simulated')),403)
        self.assertEqual(post(dict(drink,kind='fault',volume_ml=None)),403)
        self.assertEqual(post(drink),201)
        self.assertEqual(post(drink),200)
        self.assertEqual(post(dict(drink,volume_ml=200)),409)
        self.assertEqual(len(contexts),1)
        self.assertEqual(contexts[0]['drink_count'],1)
        self.assertEqual(contexts[0]['drank_ml'],150)
        rem=self.request('GET','/api/reminder','admin-secret')[1]['reminder']
        self.assertEqual(rem['interval_minutes'],25)
        self.assertEqual(rem['repeat_enabled'],1)
        self.assertEqual(self.request('GET','/api/events','device-secret')[0],401)
        self.assertEqual(self.request('GET','/api/summary','admin-secret')[1]['drinking_ml'],150)
        self.assertEqual(self.request('GET','/api/notifications','admin-secret')[1]['items'],[])

    def test_reminder_commits_fire_before_model_and_checks_schedule_snapshot(self):
        entered=threading.Event(); release=threading.Event()
        def model(c):
            entered.set(); release.wait(3)
            return {'next_reminder_minutes':40,'suggested_ml':200,'reason':'Next reminder.'}
        self.server.hydration_provider=model
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO reminders VALUES (1,30,?,1)',(time.time()-1,))
        try:
            self.assertTrue(entered.wait(2))
            # A separate writer succeeds while inference is blocked; fire is durable.
            with closing(sqlite3.connect(self.path,timeout=.2)) as db, db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM notification_jobs WHERE kind='reminder'").fetchone()[0],1)
                db.execute('UPDATE reminders SET repeat_enabled=0,next_due=?',(time.time()+900,))
        finally: release.set()
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            with closing(sqlite3.connect(self.path)) as db:
                if db.execute('SELECT COUNT(*) FROM advice_log').fetchone()[0]: break
            time.sleep(.02)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT repeat_enabled FROM reminders').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM advice_log').fetchone()[0],1)

    def test_repeating_fire_uses_model_to_schedule_next_and_delivers_once(self):
        contexts=[]
        def model(c):
            contexts.append(c)
            return {'next_reminder_minutes':42,'suggested_ml':230,'reason':'Next interval.'}
        model.model='mock-reminder-model'
        self.server.hydration_provider=model
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO reminders VALUES (1,30,?,1)',(time.time()-1,))
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            notes=self.request('GET','/api/notifications','admin-secret')[1]['items']
            if notes and notes[0]['status']=='delivered': break
            time.sleep(.03)
        self.assertEqual(len(notes),1); self.assertEqual(notes[0]['status'],'delivered')
        self.assertEqual(len(contexts),1); self.assertEqual(contexts[0]['last_interval_minutes'],30)
        self.assertIsNotNone(contexts[0]['last_reminder_at'])
        rem=self.request('GET','/api/reminder','admin-secret')[1]['reminder']
        self.assertEqual(rem['interval_minutes'],42)
        decision=self.request('GET','/api/advice','admin-secret')[1]['advice']
        self.assertAlmostEqual(rem['next_due'],decision['timestamp']+42*60)
        with closing(sqlite3.connect(self.path)) as db:
            model_id,fallback,output=db.execute('SELECT model,fallback,output_json FROM advice_log').fetchone()
        self.assertEqual(model_id,'mock-reminder-model'); self.assertEqual(fallback,0)
        self.assertFalse(json.loads(output)['actuation_allowed'])

    def test_voice_device_status_does_not_fabricate_connection(self):
        status,answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว สถานะอุปกรณ์'})
        self.assertEqual(status,200); self.assertEqual(answer['intent'],'status')
        self.assertFalse(answer['online']); self.assertIn('ออฟไลน์',answer['reply'])
        self.request('POST','/api/telemetry','device-secret',self.sample)
        _,answer=self.request('POST','/api/voice','admin-secret',{'text':'แก้ว device status'})
        self.assertTrue(answer['online'])


if __name__ == '__main__':
    unittest.main()
