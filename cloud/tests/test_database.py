"""Backend selection/SQL adaptation tests need neither psycopg nor Postgres."""
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import closing
from unittest.mock import Mock, MagicMock, patch
from kaew.database import Target, connect, postgres_sql, PostgresConnection, verify_postgres


class DatabaseTest(unittest.TestCase):
    def test_unset_database_url_uses_sqlite_without_importing_psycopg(self):
        with patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as directory:
            target = Target.from_environment(directory + '/local.sqlite3')
            with patch.dict(sys.modules, {'psycopg': None}), closing(connect(target)) as db, db:
                db.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)')
                db.execute('INSERT INTO test VALUES (?,?)', (1, 'local'))
                self.assertEqual(db.execute('SELECT value FROM test WHERE id=?', (1,)).fetchone()['value'], 'local')
                self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0], 1)

    def test_url_selects_postgres_and_is_hidden_from_target_repr(self):
        # Invalid domain with no password: never connect to an account in tests.
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://example.invalid/test?sslmode=require'}):
            target = Target.from_environment('unused.sqlite3')
        self.assertTrue(target.url)
        self.assertNotIn('example.invalid', repr(target))

    def test_placeholder_translation_preserves_sql_literals_and_comments(self):
        sql = "SELECT ?, '?' AS literal, 'it''s ? 50%' AS text, \"?\" -- ?\n/* ? */ WHERE value=? AND note=$body$?$body$"
        self.assertEqual(postgres_sql(sql), "SELECT %s, '?' AS literal, 'it''s ? 50%%' AS text, \"?\" -- ?\n/* ? */ WHERE value=%s AND note=$body$?$body$")

    def test_postgres_connect_uses_dict_rows_timeouts_and_no_preparation(self):
        raw = Mock()
        driver = types.ModuleType('psycopg')
        driver.Error = type('DriverError', (Exception,), {})
        driver.connect = Mock(return_value=raw)
        rows = types.ModuleType('psycopg.rows'); rows.dict_row = object()
        with patch.dict(sys.modules, {'psycopg': driver, 'psycopg.rows': rows}):
            db = connect(Target('unused', 'postgresql://example.invalid/test?sslmode=require'))
        args, options = driver.connect.call_args
        self.assertEqual(args, ('postgresql://example.invalid/test?sslmode=require',))
        self.assertIs(options['row_factory'], rows.dict_row)
        self.assertTrue(options['autocommit'])
        self.assertIsNone(options['prepare_threshold'])
        self.assertEqual(options['connect_timeout'], 10)
        self.assertIsInstance(db, PostgresConnection)

    def test_missing_optional_driver_has_actionable_error(self):
        with patch.dict(sys.modules, {'psycopg': None}), self.assertRaisesRegex(RuntimeError, 'cloud/requirements.txt'):
            connect(Target('unused', 'postgresql://example.invalid/test'))

    def test_driver_errors_are_redacted_and_retryable(self):
        driver = types.ModuleType('psycopg')
        driver.Error = type('DriverError', (Exception,), {})
        driver.connect = Mock(side_effect=driver.Error('private connection detail'))
        rows = types.ModuleType('psycopg.rows'); rows.dict_row = object()
        with patch.dict(sys.modules, {'psycopg': driver, 'psycopg.rows': rows}):
            with self.assertRaises(sqlite3.OperationalError) as caught:
                connect(Target('unused', 'postgresql://example.invalid/test'))
        self.assertNotIn('private connection detail', str(caught.exception))

    def test_transaction_and_writer_lock_preserve_parameter_binding(self):
        raw = MagicMock()
        db = PostgresConnection(raw, RuntimeError)
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('SELECT ? AS value', ('bound value',))
        self.assertEqual(raw.execute.call_args_list[0].args, ('SELECT pg_advisory_xact_lock(2110356)', ()))
        self.assertEqual(raw.execute.call_args_list[1].args, ('SELECT %s AS value', ('bound value',)))
        raw.transaction.return_value.__exit__.assert_called_once_with(None, None, None)

    def test_missing_schema_points_to_deliverable(self):
        raw = Mock(); raw.execute.side_effect = RuntimeError('missing table')
        with patch('kaew.database.connect', return_value=PostgresConnection(raw, RuntimeError)):
            with self.assertRaisesRegex(RuntimeError, 'cloud/migrations/postgres/001_initial.sql'):
                verify_postgres(Target('unused', 'postgresql://example.invalid/test'))
