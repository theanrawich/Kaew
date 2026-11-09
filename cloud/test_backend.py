import json
import os
import tempfile
import threading
import unittest
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
from server import create_server
from outbox import Outbox


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


if __name__ == '__main__':
    unittest.main()
