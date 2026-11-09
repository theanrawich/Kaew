"""Local development telemetry service. Not an Internet-facing production server."""
import hmac
from contextlib import closing
import json
import math
import os
import sqlite3
import time
import threading
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
        if version > 3: raise RuntimeError('database schema newer than server')
        if version == 0:
            db.executescript((ROOT / 'migrations/001_initial.sql').read_text(encoding='utf-8'))
            version = 1
        if version == 1:
            db.executescript((ROOT / 'migrations/002_events.sql').read_text(encoding='utf-8'))
            version = 2
        if version == 2:
            db.executescript((ROOT / 'migrations/003_goal.sql').read_text(encoding='utf-8'))
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
        path = urlsplit(self.path).path
        if path in ('/api/events', '/api/reminder', '/api/goal'):
            data = self.read_json()
            if not self.authorized(self.server.admin_token): return self.reply(401, {'error': 'unauthorized'})
            if path == '/api/events': return self.add_event(data)
            if path == '/api/goal': return self.set_goal(data)
            return self.set_reminder(data)
        if path != '/api/telemetry': return self.reply(404, {'error': 'not_found'})
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

    def add_event(self, data):
        if not isinstance(data, dict) or set(data) != {'event_id','kind','source','volume_ml'}:
            return self.reply(400, {'error':'invalid_event'})
        ident, kind, source, volume = data['event_id'], data['kind'], data['source'], data['volume_ml']
        if not isinstance(ident,str) or not ident or len(ident)>80 or kind not in ('drink','fault') or source not in ('measured','estimated','simulated'):
            return self.reply(400, {'error':'invalid_event'})
        if kind == 'drink' and (type(volume) not in (int,float) or not math.isfinite(volume) or not 0 < volume <= 1000):
            return self.reply(400, {'error':'invalid_event'})
        if kind == 'fault' and volume is not None: return self.reply(400, {'error':'invalid_event'})
        with closing(connect(self.server.db_path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT kind,source,volume_ml FROM events WHERE id=?',(ident,)).fetchone()
            if old:
                if tuple(old) != (kind, source, volume): return self.reply(409, {'error':'duplicate_conflict'})
                return self.reply(200, {'status':'duplicate'})
            db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(ident,kind,source,volume,time.time()))
        return self.reply(201, {'status':'stored'})

    def set_reminder(self, data):
        if not isinstance(data,dict) or set(data)!={'interval_minutes','next_due'} or type(data['interval_minutes']) is not int or not 1<=data['interval_minutes']<=1440 or type(data['next_due']) not in (int,float) or not math.isfinite(data['next_due']) or not 0<data['next_due']<time.time()+86400*366:
            return self.reply(400, {'error':'invalid_reminder'})
        with closing(connect(self.server.db_path)) as db, db:
            db.execute('INSERT OR REPLACE INTO reminders VALUES (1,?,?)',(data['interval_minutes'],data['next_due']))
        return self.reply(200, {'status':'saved'})

    def set_goal(self, data):
        if not isinstance(data,dict) or set(data)!={'goal_ml'} or type(data['goal_ml']) is not int or not 100 <= data['goal_ml'] <= 10000:
            return self.reply(400, {'error':'invalid_goal'})
        with closing(connect(self.server.db_path)) as db, db:
            db.execute("INSERT OR REPLACE INTO settings VALUES ('goal_ml',?)",(data['goal_ml'],))
        return self.reply(200, {'status':'saved'})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            body = (ROOT / 'dashboard.html').read_bytes()
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'")
            self.end_headers(); self.wfile.write(body); return
        if path == '/api/health': return self.reply(200, {'status': 'ok'})
        if path not in ('/api/status', '/api/telemetry','/api/events','/api/summary','/api/notifications','/api/reminder','/api/goal'): return self.reply(404, {'error': 'not_found'})
        if not self.authorized(self.server.admin_token): return self.reply(401, {'error': 'unauthorized'})
        with closing(connect(self.server.db_path)) as db, db:
            if path == '/api/goal':
                row=db.execute("SELECT value FROM settings WHERE key='goal_ml'").fetchone()
                return self.reply(200, {'goal_ml': row['value'] if row else None})
            if path == '/api/events': return self.reply(200, {'items':[dict(x) for x in db.execute('SELECT * FROM events ORDER BY received_at DESC LIMIT 100')]})
            if path == '/api/notifications': return self.reply(200, {'items':[dict(x) for x in db.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 100')]})
            if path == '/api/reminder':
                row = db.execute('SELECT interval_minutes,next_due FROM reminders WHERE id=1').fetchone()
                return self.reply(200, {'reminder':dict(row) if row else None})
            if path == '/api/summary':
                start = time.time()-86400
                rows = db.execute("SELECT source,COALESCE(SUM(volume_ml),0) AS total FROM events WHERE kind='drink' AND received_at>=? GROUP BY source",(start,)).fetchall()
                totals = {r['source']:r['total'] for r in rows}
                return self.reply(200, {'drinking_ml':sum(totals.values()),'by_source':totals,'window':'last_24_hours'})
            if path == '/api/telemetry':
                rows = db.execute('SELECT * FROM telemetry ORDER BY id DESC LIMIT 100').fetchall()
                return self.reply(200, {'items': [dict(row) for row in rows]})
            row = db.execute('SELECT * FROM devices WHERE id=?', ('node-1',)).fetchone()
            device = dict(row); device['online'] = row['last_seen'] is not None and time.time() - row['last_seen'] < 30
            return self.reply(200, {'device': device})


class KaewServer(ThreadingHTTPServer):
    def server_close(self):
        self.stop_reminders.set()
        self.reminder_thread.join(timeout=3)
        super().server_close()


def reminder_loop(server):
    while not server.stop_reminders.wait(0.25):
        try:
            with closing(connect(server.db_path)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT interval_minutes,next_due FROM reminders WHERE id=1').fetchone()
                now=time.time()
                if row and row['next_due'] <= now:
                    db.execute('INSERT OR IGNORE INTO notifications(reminder_due,provider,created_at) VALUES (?,\'mock\',?)',(row['next_due'],now))
                    db.execute('UPDATE reminders SET next_due=? WHERE id=1',(now+row['interval_minutes']*60,))
        except sqlite3.Error:
            continue


def create_server(host, port, db_path, device_token, admin_token):
    if not device_token or not admin_token or device_token == admin_token: raise ValueError('distinct tokens required')
    migrate(db_path)
    server = KaewServer((host, port), Handler)
    server.db_path, server.device_token, server.admin_token = db_path, device_token, admin_token
    server.stop_reminders = threading.Event()
    server.reminder_thread = threading.Thread(target=reminder_loop,args=(server,),daemon=True)
    server.reminder_thread.start()
    return server


def main():
    device_token = os.environ.get('KAEW_DEVICE_TOKEN', '')
    admin_token = os.environ.get('KAEW_ADMIN_TOKEN', '')
    db_path = os.environ.get('KAEW_DB_PATH', str(ROOT / 'kaew.sqlite3'))
    host = os.environ.get('KAEW_HOST', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost', '::1') and os.environ.get('KAEW_DEV_ALLOW_INSECURE_LAN') != '1':
        raise ValueError('non-loopback HTTP requires KAEW_DEV_ALLOW_INSECURE_LAN=1')
    server = create_server(host, int(os.environ.get('KAEW_PORT', '8080')), db_path, device_token, admin_token)
    print('Kaew development HTTP on %s:%s (no TLS)' % (host, server.server_port), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
