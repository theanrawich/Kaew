"""Deterministic advice API + fake-pump software loop. No real AI/pump claims."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from kaew.gateway_advice import parse_gateway_query, project_advice
from kaew.server import create_server

QUERY = 'gateway=1&boot_session=77&request_id=1&cup_session=1&nonce=123'


class GatewayProjectionTest(unittest.TestCase):
    def row(self, **changes):
        return dict({'id':1, 'created_at':1000, 'fallback':0,
                     'output_json':json.dumps({'suggested_ml':180,'source':'model','fallback':False,'reason':'private context'})}, **changes)

    def test_small_read_only_projection_and_request_binding(self):
        result = project_advice(self.row(),parse_gateway_query(QUERY),1000.125)
        self.assertEqual(result, dict(version=1,boot_session=77,request_id=1,cup_session=1,nonce=123,
                                      advice_id=1,age_ms=125,suggested_ml=180,model_backed=True,actuation_allowed=False))
        self.assertLess(len(json.dumps(result)),512)
        self.assertNotIn('reason',result)

    def test_query_requires_exact_nonzero_uint32_identifiers(self):
        for query in ['',QUERY+'&extra=1',QUERY+'&nonce=123',QUERY.replace('nonce=123','nonce=0'),
                      QUERY.replace('nonce=123','nonce=-1'),QUERY.replace('nonce=123','nonce=4294967296'),
                      QUERY.replace('nonce=123','nonce=01'),QUERY.replace('gateway=1','gateway=2')]:
            with self.subTest(query=query), self.assertRaises(ValueError):
                parse_gateway_query(query)

    def test_old_future_invalid_and_missing_decisions_are_rejected(self):
        for row in [None,self.row(created_at=879.999),self.row(created_at=1000.1),self.row(created_at=float('nan')),
                    self.row(output_json='{}'),self.row(output_json='null'),self.row(output_json='{'),
                    self.row(output_json=json.dumps({'suggested_ml':True})),self.row(id=4294967296)]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                project_advice(row,parse_gateway_query(QUERY),1000)

    def test_fallback_is_labeled_and_cannot_grant_actuation(self):
        row=self.row(fallback=1,output_json=json.dumps({'suggested_ml':200,'source':'model','actuation_allowed':True}))
        result=project_advice(row,parse_gateway_query(QUERY),1000)
        self.assertFalse(result['model_backed'])
        self.assertFalse(result['actuation_allowed'])
        for fallback in (None, '0'):
            result=project_advice(self.row(fallback=fallback),parse_gateway_query(QUERY),1000)
            self.assertFalse(result['model_backed'])


class DeterministicModel:
    model='synthetic-integration-provider'
    ml=180
    def __call__(self, context):
        return {'next_reminder_minutes':45,'suggested_ml':self.ml,'reason':'Synthetic test decision only'}


class GatewayAdviceApiTest(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=str(Path(self.directory.name)/'test.sqlite3')
        self.model=DeterministicModel()
        self.server=create_server('127.0.0.1',0,self.path,'device-test','admin-test',hydration_provider=self.model)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.directory.cleanup()

    def request(self, method, path, token, data=None):
        body=None if data is None else json.dumps(data).encode()
        req=urllib.request.Request(self.url+path,data=body,method=method,
                                   headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            response=urllib.request.urlopen(req,timeout=3)
        except urllib.error.HTTPError as error:
            response=error
        with response:
            return response.status,json.load(response)

    def decision(self, simulated=False):
        with closing(sqlite3.connect(self.path)) as db:
            next_id=db.execute('SELECT COUNT(*) FROM events').fetchone()[0]+1
        event={'event_id':f'test-drink-{next_id}','kind':'drink',
               'source':'simulated' if simulated else 'measured','volume_ml':100}
        self.assertEqual(self.request('POST','/api/events','admin-test',event)[0],201)
        status,data=self.request('GET','/api/advice','admin-test')
        self.assertEqual(status,200)
        self.assertFalse(data['advice']['actuation_allowed'])
        return data

    def test_device_can_read_only_bound_projection_without_admin_history(self):
        self.decision()
        status,result=self.request('GET','/api/advice?'+QUERY,'device-test')
        self.assertEqual(status,200)
        self.assertEqual(result['suggested_ml'],180)
        self.assertTrue(result['model_backed'])
        self.assertFalse(result['actuation_allowed'])
        self.assertNotIn('reason',result)
        self.assertEqual(self.request('GET','/api/advice','device-test')[0],401)
        self.assertEqual(self.request('GET','/api/events','device-test')[0],401)
        self.assertEqual(self.request('POST','/api/advice','device-test',{'include_simulated':False})[0],404)
        self.assertEqual(self.request('GET','/api/advice?'+QUERY,'wrong-token')[0],401)
        self.assertIn('advice',self.request('GET','/api/advice','admin-test')[1])

    def test_no_advice_bad_query_and_stale_advice_fail_closed(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM advice_log')
        self.assertEqual(self.request('GET','/api/advice?'+QUERY,'device-test')[0],409)
        self.assertEqual(self.request('GET','/api/advice?'+QUERY+'&nonce=1','device-test')[0],400)
        self.decision()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE advice_log SET created_at=?',(time.time()-121,))
        self.assertEqual(self.request('GET','/api/advice?'+QUERY,'device-test')[0],409)

    def test_simulated_decisions_not_exported_and_fallback_marked(self):
        status, initial = self.request('GET','/api/advice?'+QUERY,'device-test')
        self.assertEqual(status,200)
        self.decision(simulated=True)
        status, after_simulation = self.request('GET','/api/advice?'+QUERY,'device-test')
        self.assertEqual(status,200)
        self.assertEqual(after_simulation['advice_id'],initial['advice_id'])
        self.server.hydration_provider=None
        self.decision()
        status,data=self.request('GET','/api/advice?'+QUERY,'device-test')
        self.assertEqual(status,200)
        self.assertFalse(data['model_backed'])

    def test_http_to_cpp_safety_loop_uses_model_volume_and_stops_fake_pump(self):
        compiler=shutil.which('g++')
        if not compiler:
            self.skipTest('g++ required for C++ fake-pump integration probe')
        root=Path(__file__).resolve().parents[2]
        executable=Path(self.directory.name)/'ai-refill-probe.exe'
        subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',f'-I{root / "firmware/include"}',
                        str(root/'firmware/test/ai_refill_probe.cpp'),'-o',str(executable)],check=True,capture_output=True)
        for ml in (120,240,400):
            self.model.ml=ml
            self.decision()
            status,proposal=self.request('GET','/api/advice?'+QUERY,'device-test')
            self.assertEqual(status,200)
            result=subprocess.run([str(executable)],input=json.dumps(proposal),text=True,capture_output=True,check=True)
            result=json.loads(result.stdout)
            self.assertTrue(result['simulation'])
            self.assertEqual(result['started'],ml<=300)
            if ml<=300:
                self.assertEqual(result['target_g'],100+ml)
            self.assertFalse(result['pump_after_target'])
