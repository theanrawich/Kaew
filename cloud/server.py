"""Local development telemetry service. Not an Internet-facing production server."""
import hmac
from contextlib import closing
import json
import math
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
MAX_BODY = 4096


def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def migrate(path):
    with closing(connect(path)) as db, db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > 1: raise RuntimeError('database schema newer than server')
        if version == 0:
            db.executescript((ROOT / 'migrations/001_initial.sql').read_text(encoding='utf-8'))
        db.execute('INSERT OR IGNORE INTO devices(id) VALUES (?)', ('node-1',))


def validate(data):
    if not isinstance(data, dict) or set(data) != {'device_id', 'session', 'seq', 'level', 'temperature_c', 'tds_adc'}: return False
    integer = lambda n, lo, hi: type(n) is int and lo <= n <= hi
    temp = data['temperature_c']
    return (isinstance(data['device_id'], str) and integer(data['session'], 1, 4294967295)
            and integer(data['seq'], 0, 4294967295) and data['level'] in ('wet', 'dry', 'unknown')
            and (temp is None or (type(temp) in (int, float) and math.isfinite(temp) and -55 <= temp <= 125))
            and integer(data['tds_adc'], 0, 4095))


class Handler(BaseHTTPRequestHandler):
    server_version = 'KaewLocal/0.1'

    def log_message(self, format, *args):
        pass

    def reply(self, status, obj):
        body = json.dumps(obj, allow_nan=False, separators=(',', ':')).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def authorized(self, secret):
        header = self.headers.get('Authorization', '')
        return hmac.compare_digest(header, 'Bearer ' + secret)

    def read_json(self):
        try:
            length = int(self.headers.get('Content-Length', '-1'))
            if length < 1 or length > MAX_BODY: return None
            return json.loads(self.rfile.read(length), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError): return None

    def do_POST(self):
        if urlsplit(self.path).path != '/api/telemetry': return self.reply(404, {'error': 'not_found'})
        data = self.read_json()
        if not self.authorized(self.server.device_token): return self.reply(401, {'error': 'unauthorized'})
        if not validate(data): return self.reply(400, {'error': 'invalid_telemetry'})
        if data['device_id'] != 'node-1': return self.reply(403, {'error': 'unknown_device'})
        now = time.time()
        with closing(connect(self.server.db_path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT level, temperature_c, tds_adc FROM telemetry WHERE device_id=? AND session=? AND seq=?',
                                  (data['device_id'], data['session'], data['seq'])).fetchone()
            if existing:
                if (existing['level'], existing['temperature_c'], existing['tds_adc']) != (data['level'], data['temperature_c'], data['tds_adc']):
                    return self.reply(409, {'error': 'duplicate_conflict'})
                return self.reply(200, {'status': 'duplicate'})
            db.execute('INSERT INTO telemetry(device_id, session, seq, level, temperature_c, tds_adc, received_at) VALUES (?,?,?,?,?,?,?)',
                       (data['device_id'], data['session'], data['seq'], data['level'], data['temperature_c'], data['tds_adc'], now))
            db.execute('UPDATE devices SET last_seen=? WHERE id=?', (now, data['device_id']))
        self.reply(201, {'status': 'stored'})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            body = (ROOT / 'dashboard.html').read_bytes()
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'")
            self.end_headers(); self.wfile.write(body); return
        if path == '/api/health': return self.reply(200, {'status': 'ok'})
        if path not in ('/api/status', '/api/telemetry'): return self.reply(404, {'error': 'not_found'})
        if not self.authorized(self.server.admin_token): return self.reply(401, {'error': 'unauthorized'})
        with closing(connect(self.server.db_path)) as db, db:
            if path == '/api/telemetry':
                rows = db.execute('SELECT * FROM telemetry ORDER BY id DESC LIMIT 100').fetchall()
                return self.reply(200, {'items': [dict(row) for row in rows]})
            row = db.execute('SELECT * FROM devices WHERE id=?', ('node-1',)).fetchone()
            device = dict(row); device['online'] = row['last_seen'] is not None and time.time() - row['last_seen'] < 30
            return self.reply(200, {'device': device})


def create_server(host, port, db_path, device_token, admin_token):
    if not device_token or not admin_token or device_token == admin_token: raise ValueError('distinct tokens required')
    migrate(db_path)
    server = ThreadingHTTPServer((host, port), Handler)
    server.db_path, server.device_token, server.admin_token = db_path, device_token, admin_token
    return server


def main():
    device_token = os.environ.get('KAEW_DEVICE_TOKEN', '')
    admin_token = os.environ.get('KAEW_ADMIN_TOKEN', '')
    db_path = os.environ.get('KAEW_DB_PATH', str(ROOT / 'kaew.sqlite3'))
    server = create_server('127.0.0.1', int(os.environ.get('KAEW_PORT', '8080')), db_path, device_token, admin_token)
    print('Kaew local service on http://127.0.0.1:%s' % server.server_port, flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
