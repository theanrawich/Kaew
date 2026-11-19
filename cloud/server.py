"""Checkpoint telemetry service: local HTTP or private HTTP behind a trusted HTTPS edge."""
import hmac
from contextlib import closing
import json
import math
import os
import sqlite3
import time
import threading
from database import connect, Target, verify_postgres
from notifications import MockProvider, TelegramProvider
from voice import parse_text
from hydration_ai import recommend, select_provider
from gateway_advice import parse_gateway_query, project_advice
from datetime import datetime
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
MAX_BODY = 4096


def migrate(path):
    if isinstance(path, Target) and path.url:
        verify_postgres(path)
        return
    with closing(connect(path)) as db, db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > 8: raise RuntimeError('database schema newer than server')
        if version == 0:
            db.executescript((ROOT / 'migrations/001_initial.sql').read_text(encoding='utf-8'))
            version = 1
        if version == 1:
            db.executescript((ROOT / 'migrations/002_events.sql').read_text(encoding='utf-8'))
            version = 2
        if version == 2:
            db.executescript((ROOT / 'migrations/003_goal.sql').read_text(encoding='utf-8'))
            version = 3
        if version == 3:
            db.executescript((ROOT / 'migrations/004_notification_jobs.sql').read_text(encoding='utf-8'))
            version = 4
        if version == 4:
            db.executescript((ROOT / 'migrations/005_one_shot.sql').read_text(encoding='utf-8'))
            version = 5
        if version == 5:
            db.executescript((ROOT / 'migrations/006_telemetry_source.sql').read_text(encoding='utf-8'))
            version = 6
        if version == 6:
            db.executescript((ROOT / 'migrations/007_advice.sql').read_text(encoding='utf-8'))
            version = 7
        if version == 7:
            db.executescript((ROOT / 'migrations/008_advice_loop.sql').read_text(encoding='utf-8'))
        db.execute('INSERT INTO devices(id) VALUES (?) ON CONFLICT (id) DO NOTHING', ('node-1',))


def validate(data):
    if not isinstance(data, dict) or set(data) not in ({'device_id','session','seq','level','temperature_c','tds_adc'}, {'device_id','session','seq','level','temperature_c','tds_adc','source'}): return False
    integer = lambda n, lo, hi: type(n) is int and lo <= n <= hi
    temp = data['temperature_c']
    return (isinstance(data['device_id'], str) and integer(data['session'], 1, 4294967295)
            and integer(data['seq'], 0, 4294967295) and data['level'] in ('wet', 'dry', 'unknown')
            and (temp is None or (type(temp) in (int, float) and math.isfinite(temp) and -55 <= temp <= 125))
            and (integer(data['tds_adc'], 0, 4095) or data['tds_adc'] == 65535 and type(data['tds_adc']) is int) and data.get('source','unknown') in ('unknown','device','simulated'))


def queue_notification(db, key, kind, text, provider, now):
    if kind in ('low_water','fault','offline','sensor_range','sensor_error'):
        last=db.execute('SELECT MAX(created_at) AS last FROM notification_jobs WHERE kind=?',(kind,)).fetchone()['last']
        if last is not None and now-last < 300: return
    db.execute('INSERT INTO notification_jobs(id,kind,text,status,next_attempt,created_at,provider) VALUES (?,?,?,\'pending\',?,?,?) ON CONFLICT (id) DO NOTHING',
               (key,kind,text,now,now,provider))
    
def _env_float(name, default):
    try: return float(os.environ.get(name, default))
    except (TypeError, ValueError): return default


def check_sensor_alerts(db, data, now, provider_name):
    """Edge-triggered alerts: one message when a reading goes bad, one when it recovers."""
    sim = ' (ข้อมูลจำลอง)' if data.get('source') == 'simulated' else ''
    key = '%s:%s' % (data['session'], data['seq'])
    lo, hi = _env_float('KAEW_TEMP_MIN_C', 5.0), _env_float('KAEW_TEMP_MAX_C', 45.0)
    tds_max = _env_float('KAEW_TDS_ADC_MAX', 0.0)  # 0 = disabled (ADC is uncalibrated)
    temp, adc = data['temperature_c'], data['tds_adc']
    state = lambda k: (db.execute('SELECT value FROM alert_state WHERE key=?', (k,)).fetchone() or {'value': '0'})['value']
    setstate = lambda k, v: db.execute('INSERT INTO alert_state VALUES (?,?) ON CONFLICT (key) DO UPDATE SET value=excluded.value', (k, v))
    # sensor fault: TDS sentinel 65535 or missing temperature
    bad = adc == 65535 or temp is None
    if bad and state('sensor_error') != '1':
        queue_notification(db, 'sensor_error:' + key, 'sensor_error', 'แก้ว: เซนเซอร์ผิดพลาดหรืออ่านค่าไม่ได้ โปรดตรวจสายเซนเซอร์' + sim, provider_name, now)
    setstate('sensor_error', '1' if bad else '0')
    # out-of-range: temperature outside [lo, hi] or TDS above the optional limit
    out = (temp is not None and not lo <= temp <= hi) or (tds_max > 0 and adc != 65535 and adc > tds_max)
    if out and state('sensor_range') != '1':
        parts = []
        if temp is not None and not lo <= temp <= hi: parts.append('อุณหภูมิน้ำ %.1f °C (เกณฑ์ %g-%g)' % (temp, lo, hi))
        if tds_max > 0 and adc != 65535 and adc > tds_max: parts.append('ค่า TDS ดิบ %d (เกินเกณฑ์ %g)' % (adc, tds_max))
        queue_notification(db, 'range:' + key, 'sensor_range', 'แก้ว: ค่าน้ำผิดปกติ ' + ' / '.join(parts) + sim, provider_name, now)
    setstate('sensor_range', '1' if out else '0')

def reminder_snapshot(db):
    row=db.execute('SELECT interval_minutes,next_due,repeat_enabled FROM reminders WHERE id=1').fetchone()
    return tuple(row[k] for k in ('interval_minutes','next_due','repeat_enabled')) if row else None


def apply_advice(server, include_simulated=False, automatic=False, expected_reminder=None):
    """Inference runs outside DB transactions; logging and conditional schedule commit together.

    Serialize in-process decisions and compare the reminder snapshot after inference
    so a concurrent voice/manual reminder is never overwritten by stale inference.
    """
    with server.advice_lock:
        now=time.time()
        with closing(connect(server.db_path)) as db:
            before=reminder_snapshot(db)
            if automatic and ((before and not before[2]) or
                              (expected_reminder is not None and before!=expected_reminder)):
                return None
            sources=('measured','estimated','simulated') if include_simulated else ('measured','estimated')
            placeholders=','.join('?' for _ in sources)
            row=db.execute("SELECT COALESCE(SUM(volume_ml),0) AS total,COUNT(*) AS count FROM events WHERE kind='drink' AND received_at>=? AND source IN ("+placeholders+")",(now-86400,*sources)).fetchone()
            last=db.execute("SELECT MAX(received_at) AS last FROM events WHERE kind='drink' AND source IN ("+placeholders+")",sources).fetchone()['last']
            goal=db.execute("SELECT value FROM settings WHERE key='goal_ml'").fetchone()
            telemetry_sources=('device','unknown','simulated') if include_simulated else ('device','unknown')
            telemetry=db.execute("SELECT temperature_c,level,source FROM telemetry WHERE source IN ("+','.join('?' for _ in telemetry_sources)+") ORDER BY id DESC LIMIT 1",telemetry_sources).fetchone()
            previous=db.execute("SELECT MAX(created_at) AS last FROM notification_jobs WHERE kind='reminder'").fetchone()['last']
            context={'goal_ml':goal['value'] if goal else None,'drank_ml':min(row['total'],20000),
                     'drink_count':row['count'],'minutes_since_drink':min(max((now-last)/60,0),10080) if last is not None else None,
                     'cup_ml':None,'profile':'balanced','time_of_day':datetime.fromtimestamp(now,ZoneInfo('Asia/Bangkok')).strftime('%H:%M'),
                     'timezone':'Asia/Bangkok','temperature_c':telemetry['temperature_c'] if telemetry else None,
                     'tank_level':telemetry['level'] if telemetry else 'unknown',
                     'telemetry_source':telemetry['source'] if telemetry else None,
                     'last_reminder_at':previous,'last_interval_minutes':before[0] if before else None}
        result=recommend(context,server.hydration_provider)
        now=time.time()
        with closing(connect(server.db_path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            # A changed reminder supersedes this in-flight decision (including manual requests).
            scheduled=reminder_snapshot(db)==before
            result.update(timestamp=now,scheduled=scheduled,actuation_allowed=False)
            db.execute('INSERT INTO advice_log(created_at,input_json,output_json,simulated,model,fallback) VALUES (?,?,?,?,?,?)',
                       (now,json.dumps(context),json.dumps(result,ensure_ascii=False),int(include_simulated),result['model'],int(result['fallback'])))
            if scheduled:
                minutes=result['next_reminder_minutes']
                db.execute('INSERT INTO reminders(id,interval_minutes,next_due,repeat_enabled) VALUES (1,?,?,1) ON CONFLICT (id) DO UPDATE SET interval_minutes=excluded.interval_minutes,next_due=excluded.next_due,repeat_enabled=1',
                           (minutes,now+minutes*60))
        return result


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
        if path in ('/api/events', '/api/reminder', '/api/goal', '/api/voice', '/api/advice'):
            data = self.read_json()
            if not self.authorized(self.server.admin_token): return self.reply(401, {'error': 'unauthorized'})
            if path == '/api/events': return self.add_event(data)
            if path == '/api/goal': return self.set_goal(data)
            if path == '/api/voice': return self.voice(data)
            if path == '/api/advice': return self.advice(data)
            return self.set_reminder(data)
        if path == '/api/scale':
            data = self.read_json()
            if not self.authorized(self.server.device_token): return self.reply(401, {'error': 'unauthorized'})
            return self.add_scale(data)
        if path != '/api/telemetry': return self.reply(404, {'error': 'not_found'})
        data = self.read_json()
        if not self.authorized(self.server.device_token): return self.reply(401, {'error': 'unauthorized'})
        if not validate(data): return self.reply(400, {'error': 'invalid_telemetry'})
        if data['device_id'] != 'node-1': return self.reply(403, {'error': 'unknown_device'})
        now = time.time()
        with closing(connect(self.server.db_path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT level, temperature_c, tds_adc, source FROM telemetry WHERE device_id=? AND session=? AND seq=?',
                                  (data['device_id'], data['session'], data['seq'])).fetchone()
            if existing:
                if (existing['level'], existing['temperature_c'], existing['tds_adc'],existing['source']) != (data['level'], data['temperature_c'], data['tds_adc'],data.get('source','unknown')):
                    return self.reply(409, {'error': 'duplicate_conflict'})
                return self.reply(200, {'status': 'duplicate'})
            db.execute('INSERT INTO telemetry(device_id, session, seq, level, temperature_c, tds_adc, received_at, source) VALUES (?,?,?,?,?,?,?,?)',
                       (data['device_id'], data['session'], data['seq'], data['level'], data['temperature_c'], data['tds_adc'], now,data.get('source','unknown')))
            db.execute('UPDATE devices SET last_seen=? WHERE id=?', (now, data['device_id']))
            old_level=db.execute("SELECT value FROM alert_state WHERE key='level'").fetchone()
            if data['level']=='dry' and (not old_level or old_level['value']!='dry'):
                text = 'แก้ว: ระดับน้ำต่ำ โปรดตรวจขวดน้ำ' + (' (ข้อมูลจำลอง)' if data.get('source') == 'simulated' else '')
                queue_notification(db, 'low:%s:%s' % (data['session'],data['seq']), 'low_water', text, self.server.provider_name, now)
            db.execute("INSERT INTO alert_state VALUES ('level',?) ON CONFLICT (key) DO UPDATE SET value=excluded.value",(data['level'],))
            was_offline=db.execute("SELECT value FROM alert_state WHERE key='offline'").fetchone()
            if was_offline and was_offline['value']=='1':
                queue_notification(db, 'recovery:%s:%s' % (data['session'],data['seq']), 'recovery', 'แก้ว: อุปกรณ์กลับมาเชื่อมต่อแล้ว' + (' (ข้อมูลจำลอง)' if data.get('source') == 'simulated' else ''), self.server.provider_name, now)
            db.execute("INSERT INTO alert_state VALUES ('offline','0') ON CONFLICT (key) DO UPDATE SET value=excluded.value")
            check_sensor_alerts(db, data, now, self.server.provider_name)
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
                if (old['kind'], old['source'], old['volume_ml']) != (kind, source, volume): return self.reply(409, {'error':'duplicate_conflict'})
                return self.reply(200, {'status':'duplicate'})
            db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(ident,kind,source,volume,time.time()))
            if kind == 'fault': queue_notification(db,'fault:'+ident,'fault','แก้ว: พบเหตุขัดข้อง โปรดตรวจอุปกรณ์'+(' (ข้อมูลจำลอง)' if source=='simulated' else ''),self.server.provider_name,time.time())
        if kind == 'drink':
            apply_advice(self.server, include_simulated=(source=='simulated'), automatic=True)
        return self.reply(201, {'status':'stored'})
    def add_scale(self, data):
        # Latest gateway load-cell reading (live value, not history). Stored as JSON in alert_state.
        if (not isinstance(data, dict) or set(data) != {'weight_g', 'stable', 'cup', 'calibrated'}
                or type(data['weight_g']) not in (int, float) or not math.isfinite(data['weight_g'])
                or not -50 <= data['weight_g'] <= 1100
                or any(type(data[k]) is not bool for k in ('stable', 'cup', 'calibrated'))):
            return self.reply(400, {'error': 'invalid_scale'})
        row = {'weight_g': round(float(data['weight_g']), 1), 'stable': data['stable'],
               'cup': data['cup'], 'calibrated': data['calibrated'], 'at': time.time()}
        with closing(connect(self.server.db_path)) as db, db:
            db.execute("INSERT INTO alert_state VALUES ('scale_latest',?) ON CONFLICT (key) DO UPDATE SET value=excluded.value", (json.dumps(row),))
        return self.reply(201, {'status': 'stored'})
    
    def set_reminder(self, data):
        if not isinstance(data,dict) or set(data)!={'interval_minutes','next_due'} or type(data['interval_minutes']) is not int or not 1<=data['interval_minutes']<=1440 or type(data['next_due']) not in (int,float) or not math.isfinite(data['next_due']) or not 0<data['next_due']<time.time()+86400*366:
            return self.reply(400, {'error':'invalid_reminder'})
        with closing(connect(self.server.db_path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO reminders(id,interval_minutes,next_due,repeat_enabled) VALUES (1,?,?,1) ON CONFLICT (id) DO UPDATE SET interval_minutes=excluded.interval_minutes,next_due=excluded.next_due,repeat_enabled=excluded.repeat_enabled',(data['interval_minutes'],data['next_due']))
        return self.reply(200, {'status':'saved'})

    def set_goal(self, data):
        if not isinstance(data,dict) or set(data)!={'goal_ml'} or type(data['goal_ml']) is not int or not 100 <= data['goal_ml'] <= 10000:
            return self.reply(400, {'error':'invalid_goal'})
        with closing(connect(self.server.db_path)) as db, db:
            db.execute("INSERT INTO settings VALUES ('goal_ml',?) ON CONFLICT (key) DO UPDATE SET value=excluded.value",(data['goal_ml'],))
        return self.reply(200, {'status':'saved'})

    def voice(self, data):
        if not isinstance(data,dict) or set(data)!={'text'}: return self.reply(400, {'error':'invalid_voice'})
        intent=parse_text(data['text']); kind=intent['intent']
        if kind=='invalid': return self.reply(400, {'error':'invalid_voice'})
        if kind=='reminder':
            minutes=intent['minutes']
            with closing(connect(self.server.db_path)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO reminders(id,interval_minutes,next_due,repeat_enabled) VALUES (1,?,?,0) ON CONFLICT (id) DO UPDATE SET interval_minutes=excluded.interval_minutes,next_due=excluded.next_due,repeat_enabled=excluded.repeat_enabled',(minutes,time.time()+minutes*60))
            return self.reply(200, {'intent':kind,'minutes':minutes,'executed':True,'reply':'ได้เลย จะเตือนอีก %d นาที'%minutes})
        if kind=='level':
            with closing(connect(self.server.db_path)) as db:
                row=db.execute('SELECT level,received_at,source FROM telemetry ORDER BY id DESC LIMIT 1').fetchone()
            # Receipt time is not measurement time; delayed outbox records may already be old.
            # Expiry can invalidate a value, but cannot establish sensor freshness.
            level=row['level'] if row and 0<=time.time()-row['received_at']<5 else 'unknown'
            text={'wet':'ข้อมูลระดับล่าสุดระบุว่าพบระดับน้ำ แต่อาจล่าช้า', 'dry':'ข้อมูลระดับล่าสุดระบุว่าน้ำต่ำ แต่อาจล่าช้า','unknown':'ยังไม่ทราบระดับน้ำ'}[level]
            if row and row['source']=='simulated': text += ' (ข้อมูลจำลอง)'
            return self.reply(200, {'intent':kind,'level':level,'executed':True,'reply':text})
        if kind=='status':
            with closing(connect(self.server.db_path)) as db:
                row=db.execute("SELECT last_seen,(SELECT source FROM telemetry WHERE device_id='node-1' ORDER BY id DESC LIMIT 1) AS source FROM devices WHERE id='node-1'").fetchone()
            online=bool(row and row['last_seen'] and time.time()-row['last_seen']<30)
            text='ข้อมูลล่าสุดระบุว่าอุปกรณ์'+('ออนไลน์' if online else 'ออฟไลน์')
            if row and row['source']=='simulated': text+=' (ข้อมูลจำลอง)'
            return self.reply(200, {'intent':kind,'online':online,'executed':True,'reply':text})
        if kind=='refill': return self.reply(200, {'intent':kind,'executed':False,'reply':'ยังสั่งเติมไม่ได้ ระบบจ่ายน้ำยังไม่พร้อม'})
        if kind=='stop': return self.reply(200, {'intent':kind,'executed':False,'reply':'ยังไม่มีช่องสั่งหยุดผ่านเสียง กรุณาใช้ปุ่มหยุดจริง'})
        return self.reply(200, {'intent':kind,'executed':False,'reply':'ขออภัย กรุณาพูดอีกครั้ง'})

    def advice(self,data):
        if not isinstance(data,dict) or set(data)!={'include_simulated'} or type(data['include_simulated']) is not bool:
            return self.reply(400,{'error':'invalid_advice_request'})
        include=data['include_simulated']
        result=apply_advice(self.server,include_simulated=include)
        return self.reply(200,{'advice':result,'simulated_inputs_included':include,'actuation_allowed':False})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            body = (ROOT / 'dashboard.html').read_bytes()
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com")
            self.end_headers(); self.wfile.write(body); return
        if path == '/api/health': return self.reply(200, {'status': 'ok'})
        if path not in ('/api/status', '/api/telemetry','/api/events','/api/summary','/api/notifications','/api/reminder','/api/goal','/api/advice','/api/scale'): return self.reply(404, {'error': 'not_found'})
        if path == '/api/advice' and self.authorized(self.server.device_token):
            raw_query = urlsplit(self.path).query
            if not raw_query: return self.reply(401, {'error': 'unauthorized'})
            try:
                context = parse_gateway_query(raw_query)
            except ValueError:
                return self.reply(400, {'error': 'invalid_gateway_query'})
            with closing(connect(self.server.db_path)) as db:
                row = db.execute('SELECT id,output_json,fallback,created_at FROM advice_log WHERE simulated=0 ORDER BY id DESC LIMIT 1').fetchone()
            try:
                result = project_advice(row, context, time.time())
            except (ValueError, TypeError, KeyError):
                return self.reply(409, {'error': 'advice_unavailable'})
            return self.reply(200, result)
        if not self.authorized(self.server.admin_token): return self.reply(401, {'error': 'unauthorized'})
        with closing(connect(self.server.db_path)) as db, db:
            if path == '/api/advice':
                row=db.execute('SELECT output_json,model,fallback,created_at FROM advice_log ORDER BY id DESC LIMIT 1').fetchone()
                result=json.loads(row['output_json']) if row else None
                if result is not None:
                    result.update(model=row['model'],fallback=bool(row['fallback']),timestamp=row['created_at'],actuation_allowed=False)
                return self.reply(200,{'advice':result,'actuation_allowed':False})
            if path == '/api/scale':
                row = db.execute("SELECT value FROM alert_state WHERE key='scale_latest'").fetchone()
                if not row: return self.reply(200, {'scale': None})
                scale = json.loads(row['value']); scale['age_s'] = round(max(0, time.time() - scale['at']), 1)
                return self.reply(200, {'scale': scale})
            if path == '/api/goal':
                row=db.execute("SELECT value FROM settings WHERE key='goal_ml'").fetchone()
                return self.reply(200, {'goal_ml': row['value'] if row else None})
            if path == '/api/events':
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                try:
                    if any(len(query[key]) != 1 for key in ('since', 'limit') if key in query):
                        raise ValueError()
                    since = float(query['since'][0]) if 'since' in query else None
                    # Unix epoch through year 9999; reject unusable timestamps.
                    if since is not None and (not math.isfinite(since) or not 0 <= since <= 253402300799):
                        raise ValueError()
                    limit = int(query['limit'][0]) if 'limit' in query else (2000 if since is not None else 100)
                    if limit < 1:
                        raise ValueError()
                    limit = min(limit, 2000)
                except (ValueError, OverflowError):
                    return self.reply(400, {'error': 'invalid_events_query'})
                sql = 'SELECT * FROM events'
                params = []
                if since is not None:
                    sql += ' WHERE received_at >= ?'
                    params.append(since)
                sql += ' ORDER BY received_at DESC LIMIT ?'
                params.append(limit)
                return self.reply(200, {'items': [dict(x) for x in db.execute(sql, params)]})
            if path == '/api/notifications':
                items=[dict(x) for x in db.execute('SELECT * FROM notification_jobs ORDER BY created_at DESC LIMIT 100')]
                items += [{'id':'legacy:'+str(x['id']),'kind':'reminder','provider':x['provider'],
                           'status':'legacy_mock','created_at':x['created_at']} for x in db.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 100')]
                items.sort(key=lambda x:x['created_at'],reverse=True)
                return self.reply(200, {'items':items[:100]})
            if path == '/api/reminder':
                row = db.execute('SELECT interval_minutes,next_due,repeat_enabled FROM reminders WHERE id=1').fetchone()
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
        self.reminder_thread.join(timeout=22)
        self.delivery_thread.join(timeout=6)
        super().server_close()


def reminder_loop(server):
    while not server.stop_reminders.wait(0.25):
        try:
            fired=None
            with closing(connect(server.db_path)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT interval_minutes,next_due,repeat_enabled FROM reminders WHERE id=1').fetchone()
                now=time.time()
                if row and row['next_due'] <= now:
                    queue_notification(db,'reminder:'+str(row['next_due']),'reminder','แก้ว: ถึงเวลาดื่มน้ำแล้ว',server.provider_name,now)
                    if row['repeat_enabled']:
                        fired=(row['interval_minutes'],now+row['interval_minutes']*60,1)
                        db.execute('UPDATE reminders SET next_due=? WHERE id=1',(fired[1],))
                    else: db.execute('DELETE FROM reminders WHERE id=1')
                device=db.execute("SELECT last_seen,(SELECT source FROM telemetry WHERE device_id='node-1' ORDER BY id DESC LIMIT 1) AS source FROM devices WHERE id='node-1'").fetchone()
                state=db.execute("SELECT value FROM alert_state WHERE key='offline'").fetchone()
                if device and device['last_seen'] and now-device['last_seen']>=30 and (not state or state['value']!='1'):
                    queue_notification(db,'offline:'+str(device['last_seen']),'offline','แก้ว: อุปกรณ์ขาดการเชื่อมต่อ'+(' (ข้อมูลจำลอง)' if device['source']=='simulated' else ''),server.provider_name,now)
                    db.execute("INSERT INTO alert_state VALUES ('offline','1') ON CONFLICT (key) DO UPDATE SET value=excluded.value")
            if fired is not None:
                apply_advice(server,automatic=True,expected_reminder=fired)
        except sqlite3.Error:
            continue


def delivery_loop(server):
    while not server.stop_reminders.wait(1):
        try:
            with closing(connect(server.db_path)) as db:
                row=db.execute("SELECT * FROM notification_jobs WHERE status='pending' AND provider=? AND next_attempt<=? ORDER BY created_at LIMIT 1",(server.provider_name,time.time())).fetchone()
            if not row: continue
            success=False
            try: server.provider.send(row['text']); success=True
            except Exception: pass
            now=time.time(); attempts=row['attempts']+1
            with closing(connect(server.db_path)) as db, db:
                if success: db.execute("UPDATE notification_jobs SET status='delivered',attempts=?,delivered_at=? WHERE id=? AND status='pending'",(attempts,now,row['id']))
                else: db.execute("UPDATE notification_jobs SET status=?,attempts=?,next_attempt=? WHERE id=? AND status='pending'",('failed' if attempts>=8 else 'pending',attempts,now+min(3600,2**attempts),row['id']))
        except sqlite3.Error:
            continue


_ENV_PROVIDER = object()


def create_server(host, port, db_path, device_token, admin_token, provider=None, hydration_provider=_ENV_PROVIDER):
    if not device_token or not admin_token or device_token == admin_token: raise ValueError('distinct tokens required')
    db_path = Target.from_environment(db_path)
    migrate(db_path)
    server = KaewServer((host, port), Handler)
    server.db_path, server.device_token, server.admin_token = db_path, device_token, admin_token
    server.provider = provider or MockProvider()
    server.hydration_provider = select_provider() if hydration_provider is _ENV_PROVIDER else hydration_provider
    server.advice_lock = threading.Lock()
    server.provider_name = 'telegram' if isinstance(server.provider, TelegramProvider) else 'mock'
    server.stop_reminders = threading.Event()
    server.reminder_thread = threading.Thread(target=reminder_loop,args=(server,),daemon=True)
    server.reminder_thread.start()
    server.delivery_thread = threading.Thread(target=delivery_loop,args=(server,),daemon=True)
    server.delivery_thread.start()
    return server


def main():
    device_token = os.environ.get('KAEW_DEVICE_TOKEN', '')
    admin_token = os.environ.get('KAEW_ADMIN_TOKEN', '')
    db_path = os.environ.get('KAEW_DB_PATH', str(ROOT / 'kaew.sqlite3'))
    host = os.environ.get('KAEW_HOST', '127.0.0.1')
    edge_https = os.environ.get('KAEW_TRUST_EDGE_HTTPS') == '1'
    dev_lan = os.environ.get('KAEW_DEV_ALLOW_INSECURE_LAN') == '1'
    if host not in ('127.0.0.1', 'localhost', '::1') and not (edge_https or dev_lan):
        raise ValueError('non-loopback bind requires KAEW_TRUST_EDGE_HTTPS=1 behind TLS edge, or KAEW_DEV_ALLOW_INSECURE_LAN=1 for development')
    token=os.environ.get('KAEW_TELEGRAM_TOKEN',''); chat=os.environ.get('KAEW_TELEGRAM_CHAT_ID','')
    if bool(token)!=bool(chat): raise ValueError('both Telegram token and chat ID are required')
    provider=TelegramProvider(token,chat) if token else MockProvider()
    server = create_server(host, int(os.environ.get('KAEW_PORT', os.environ.get('PORT', '8080'))), db_path, device_token, admin_token, provider)
    mode = 'trusted HTTPS edge; internal HTTP' if edge_https else 'development HTTP; no TLS'
    print('Kaew on %s:%s (%s)' % (host, server.server_port, mode), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
