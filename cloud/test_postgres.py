"""Opt-in integration tests for a disposable *local* Postgres database only.

KAEW_TEST_POSTGRES_URL must name a dedicated loopback database: these tests
truncate its Kaew tables. DATABASE_URL by itself never enables these tests.
"""
import json
import os
from pathlib import Path
import threading
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch
from urllib.parse import urlsplit
from database import connect, Target
from server import create_server


@unittest.skipUnless(os.environ.get('KAEW_TEST_POSTGRES_URL'), 'optional local Postgres integration database not configured')
class PostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ['KAEW_TEST_POSTGRES_URL']
        if urlsplit(cls.url).hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('Postgres integration tests require a disposable loopback database')
        import psycopg
        cls.driver = psycopg
        # Applying twice validates syntax and fresh-schema idempotency with Postgres.
        schema = (Path(__file__).parent / 'migrations/postgres/001_initial.sql').read_text()
        with psycopg.connect(cls.url, autocommit=True) as db:
            db.execute(schema, prepare=False)
            db.execute(schema, prepare=False)

    def setUp(self):
        self.target = Target('unused', self.url)
        with closing(connect(self.target)) as db, db:
            db.execute('TRUNCATE telemetry, events, reminders, notifications, settings, notification_jobs, alert_state, advice_log RESTART IDENTITY')
            db.execute("UPDATE devices SET last_seen=NULL WHERE id='node-1'")
        with patch.dict(os.environ, {'DATABASE_URL': self.url}):
            self.server = create_server('127.0.0.1', 0, 'unused', 'device-test', 'admin-test')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:%d' % self.server.server_port

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def request(self, method, path, data=None, token='admin-test'):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, body, method=method,
                                     headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as result:
                return result.status, json.load(result)
        except urllib.error.HTTPError as result:
            return result.code, json.load(result)

    def test_telemetry_unsigned_ids_auth_concurrency_and_conflicts(self):
        sample = {'device_id': 'node-1', 'session': 4294967295, 'seq': 4294967295,
                  'temperature_c': 25.0, 'tds_adc': 65535, 'level': 'dry', 'source': 'simulated'}
        self.assertEqual(self.request('POST', '/api/telemetry', sample)[0], 401)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.request('POST', '/api/telemetry', sample, 'device-test')[0], range(4)))
        self.assertEqual(sorted(results), [200, 200, 200, 201])
        self.assertEqual(self.request('POST', '/api/telemetry', dict(sample, temperature_c=26), 'device-test')[0], 409)
        rows = self.request('GET', '/api/telemetry')[1]['items']
        self.assertEqual(len(rows), 1); self.assertEqual(rows[0]['session'], 4294967295)
        self.assertEqual(rows[0]['source'], 'simulated')
        self.assertEqual(self.request('GET', '/api/status')[1]['device']['online'], True)
        self.assertEqual(self.request('GET', '/api/health')[0], 200)
        with urllib.request.urlopen(self.base + '/') as response:
            self.assertIn(b'<!', response.read())

    def test_events_settings_advice_and_legacy_notifications(self):
        event = {'event_id': 'drink-1', 'kind': 'drink', 'source': 'measured', 'volume_ml': 120}
        self.assertEqual(self.request('POST', '/api/events', event)[0], 201)
        self.assertEqual(self.request('POST', '/api/events', event)[0], 200)
        self.assertEqual(self.request('POST', '/api/events', dict(event, volume_ml=130))[0], 409)
        self.assertEqual(self.request('GET', '/api/summary')[1]['drinking_ml'], 120)
        for goal in (1800, 2000):
            self.assertEqual(self.request('POST', '/api/goal', {'goal_ml': goal})[0], 200)
        self.assertEqual(self.request('GET', '/api/goal')[1]['goal_ml'], 2000)
        result = self.request('POST', '/api/advice', {'include_simulated': False})
        self.assertEqual(result[0], 200); self.assertFalse(result[1]['actuation_allowed'])
        with closing(connect(self.target)) as db, db:
            self.assertIsNotNone(db.execute('SELECT id FROM advice_log').fetchone())
            db.execute("INSERT INTO notifications(reminder_due,provider,created_at) VALUES (?,'mock',?)", (time.time(), time.time()))
        self.assertEqual(self.request('GET', '/api/notifications')[1]['items'][0]['status'], 'legacy_mock')

    def test_reminder_and_notification_worker(self):
        for minutes in (10, 20):
            result = self.request('POST', '/api/reminder', {'interval_minutes': minutes, 'next_due': time.time()+60})
            self.assertEqual(result[0], 200)
        self.assertEqual(self.request('GET', '/api/reminder')[1]['reminder']['interval_minutes'], 20)
        self.assertEqual(self.request('POST', '/api/voice', {'text': 'แก้ว อีก 30 นาทีเตือนให้ดื่มน้ำ'})[0], 200)
        with closing(connect(self.target)) as db, db:
            self.assertEqual(db.execute('SELECT repeat_enabled FROM reminders').fetchone()['repeat_enabled'], 0)
            db.execute('UPDATE reminders SET next_due=?', (time.time()-1,))
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            jobs = self.request('GET', '/api/notifications')[1]['items']
            if jobs and jobs[0]['status'] == 'delivered': break
            time.sleep(.05)
        self.assertEqual(jobs[0]['status'], 'delivered')
        self.assertIsNone(self.request('GET', '/api/reminder')[1]['reminder'])

    def test_transaction_rollback(self):
        with closing(connect(self.target)) as db:
            with self.assertRaisesRegex(ValueError, 'rollback'):
                with db:
                    db.execute("INSERT INTO settings VALUES ('rollback',?)", (1,))
                    raise ValueError('rollback')
            self.assertIsNone(db.execute("SELECT value FROM settings WHERE key='rollback'").fetchone())
