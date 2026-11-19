"""Real HTTP tests for authenticated telemetry SSE."""
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from kaew.server import create_server


class RealtimeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.server = create_server('127.0.0.1', 0, self.directory.name+'/test.db', 'device', 'admin', hydration_provider=None)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def test_auth_and_live_committed_data(self):
        for token in ('', 'device'):
            req = urllib.request.Request(self.url+'/api/telemetry/stream', headers={'Authorization':'Bearer '+token})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(req, timeout=3)
            self.assertEqual(error.exception.code, 401)
            error.exception.close()
        req = urllib.request.Request(self.url+'/api/telemetry/stream', headers={'Authorization':'Bearer admin'})
        with urllib.request.urlopen(req, timeout=3) as stream:
            self.assertEqual(stream.headers['Content-Type'], 'text/event-stream; charset=utf-8')
            self.assertEqual(stream.readline(), b'event: telemetry\n')
            self.assertEqual(json.loads(stream.readline()[6:]), {'items':[], 'scale':None})
            self.assertEqual(stream.readline(), b'\n')
            data = {'device_id':'node-1','session':1,'seq':1,'temperature_c':26.5,'tds_adc':100,'level':'wet','source':'device'}
            post = urllib.request.Request(self.url+'/api/telemetry', data=json.dumps(data).encode(), headers={'Authorization':'Bearer device','Content-Type':'application/json'})
            with urllib.request.urlopen(post, timeout=3) as response:
                self.assertEqual(response.status, 201)
            self.assertEqual(stream.readline(), b'event: telemetry\n')
            item = json.loads(stream.readline()[6:])['items'][0]
            self.assertEqual(item['temperature_c'], 26.5)
            self.assertEqual(item['source'], 'device')
            self.assertEqual(stream.readline(), b'\n')
            scale = {'weight_g':123.4, 'stable':True, 'cup':True, 'calibrated':True}
            post = urllib.request.Request(self.url+'/api/scale', data=json.dumps(scale).encode(), headers={'Authorization':'Bearer device','Content-Type':'application/json'})
            with urllib.request.urlopen(post, timeout=3) as response:
                self.assertEqual(response.status, 201)
            self.assertEqual(stream.readline(), b'event: telemetry\n')
            snapshot = json.loads(stream.readline()[6:])
            self.assertEqual(snapshot['scale']['weight_g'], 123.4)
            self.assertLess(snapshot['scale']['age_s'], 2)
            self.assertEqual(snapshot['items'][0]['seq'], 1)
        # Reconnecting gets the latest state, even without another write.
        with urllib.request.urlopen(req, timeout=3) as stream:
            self.assertEqual(stream.readline(), b'event: telemetry\n')
            snapshot = json.loads(stream.readline()[6:])
            self.assertEqual(snapshot['items'][0]['seq'], 1)
            self.assertEqual(snapshot['scale']['weight_g'], 123.4)

if __name__ == '__main__': unittest.main()
