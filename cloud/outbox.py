"""Durable local gateway outbox; not yet wired into ESP32 firmware."""
import json
import sqlite3
import urllib.error
import urllib.request
from contextlib import closing
from urllib.parse import urlsplit
from server import validate


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Outbox:
    def __init__(self, path, capacity=1000):
        if type(capacity) is not int or capacity < 1: raise ValueError('invalid capacity')
        self.path, self.capacity = path, capacity
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY, device TEXT NOT NULL, session INTEGER NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE(device,session,seq))')

    def count(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]

    def enqueue(self, data):
        if not validate(data): raise ValueError('invalid telemetry')
        body = json.dumps(data, allow_nan=False, sort_keys=True, separators=(',', ':'))
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT body FROM outbox WHERE device=? AND session=? AND seq=?', (data['device_id'], data['session'], data['seq'])).fetchone()
            if old:
                if old[0] != body: raise ValueError('duplicate conflict')
                return False
            if db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0] >= self.capacity: raise OverflowError('outbox full')
            db.execute('INSERT INTO outbox(device,session,seq,body) VALUES (?,?,?,?)', (data['device_id'], data['session'], data['seq'], body))
            return True

    def flush(self, base_url, token):
        u = urlsplit(base_url)
        if not token or not u.hostname or (u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost', '::1'))):
            raise ValueError('HTTPS required except loopback')
        sent = 0
        opener = urllib.request.build_opener(NoRedirect())
        while True:
            with closing(sqlite3.connect(self.path)) as db:
                row = db.execute('SELECT id,body FROM outbox ORDER BY id LIMIT 1').fetchone()
            if row is None: return sent
            request = urllib.request.Request(base_url.rstrip('/') + '/api/telemetry', data=row[1].encode(), method='POST',
                                             headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            try:
                with opener.open(request, timeout=2) as response:
                    if response.status not in (200, 201): return sent
            except (urllib.error.URLError, TimeoutError, OSError): return sent
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute('DELETE FROM outbox WHERE id=?', (row[0],))
            sent += 1
