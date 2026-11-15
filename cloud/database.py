"""SQLite by default; optional psycopg loaded only for an explicit Postgres target."""
from contextlib import closing
from dataclasses import dataclass, field
import os
import re
import sqlite3

SCHEMA_FILE = 'cloud/migrations/postgres/001_initial.sql'
# Checked at startup, before opening the HTTP listener or starting worker threads.
TABLE_COLUMNS = {
    'devices': 'id,last_seen',
    'telemetry': 'id,device_id,session,seq,level,temperature_c,tds_adc,received_at,source',
    'events': 'id,kind,source,volume_ml,received_at',
    'reminders': 'id,interval_minutes,next_due,repeat_enabled',
    'notifications': 'id,reminder_due,provider,created_at',
    'settings': 'key,value',
    'notification_jobs': 'id,kind,text,status,attempts,next_attempt,created_at,delivered_at,provider',
    'alert_state': 'key,value',
    'advice_log': 'id,created_at,input_json,output_json,simulated',
}


@dataclass(frozen=True)
class Target:
    path: str
    url: str = field(default='', repr=False)

    @classmethod
    def from_environment(cls, path):
        return cls(path, os.environ.get('DATABASE_URL', ''))


def postgres_sql(sql):
    """Translate qmarks outside SQL literals/comments; protect literal % for psycopg.

    Only application-owned SQL is passed here, never user input. Preserve quoted
    text, identifiers, comments and dollar-quoted bodies without interpreting ?.
    """
    token = re.compile(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*.*?\*/|(?P<tag>\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$).*?(?P=tag))", re.S)
    result, end = [], 0
    for match in token.finditer(sql):
        result.append(sql[end:match.start()].replace('%', '%%').replace('?', '%s'))
        result.append(match.group(0).replace('%', '%%'))
        end = match.end()
    result.append(sql[end:].replace('%', '%%').replace('?', '%s'))
    return ''.join(result)


class PostgresConnection:
    """Small sqlite-shaped interface; transaction context does not close the socket."""
    def __init__(self, raw, error_type):
        self.raw, self.error_type = raw, error_type

    def __enter__(self):
        self.transaction = self.raw.transaction()
        try:
            self.transaction.__enter__()
        except self.error_type:
            raise sqlite3.DatabaseError('Postgres transaction failed') from None
        return self

    def __exit__(self, *args):
        try:
            return self.transaction.__exit__(*args)
        except self.error_type:
            raise sqlite3.DatabaseError('Postgres transaction failed') from None

    def execute(self, sql, parameters=()):
        # Preserve SQLite's writer serialization for read-before-write dedup and
        # reminder/alert transitions. Transaction-level lock works with poolers.
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            sql = 'SELECT pg_advisory_xact_lock(2110356)'
        try:
            return self.raw.execute(postgres_sql(sql), parameters)
        except self.error_type:
            # Existing retry loops catch sqlite3.Error. Do not log SQL, DSNs or params.
            raise sqlite3.DatabaseError('Postgres query failed') from None

    def close(self):
        self.raw.close()


def connect(target):
    # Explicit path callers (including migration tests/outbox) always mean SQLite.
    if not isinstance(target, Target):
        target = Target(target)
    if not target.url:
        db = sqlite3.connect(target.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        return db
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        raise RuntimeError('DATABASE_URL requires pip install -r cloud/requirements.txt') from None
    try:
        # No automatic prepared statements: compatible with transaction poolers.
        raw = psycopg.connect(target.url, row_factory=dict_row, autocommit=True,
                              prepare_threshold=None, connect_timeout=10)
    except psycopg.Error:
        raise sqlite3.OperationalError('Postgres connection failed; check DATABASE_URL, SSL and network access privately') from None
    return PostgresConnection(raw, psycopg.Error)


def verify_postgres(target):
    with closing(connect(target)) as db:
        try:
            for table, columns in TABLE_COLUMNS.items():
                db.execute(f'SELECT {columns} FROM public.{table} LIMIT 0')
            if not db.execute("SELECT id FROM devices WHERE id='node-1'").fetchone():
                raise sqlite3.DatabaseError('missing provisioned device')
        except sqlite3.Error:
            raise RuntimeError(f'Postgres schema missing or inaccessible; apply {SCHEMA_FILE} first') from None
