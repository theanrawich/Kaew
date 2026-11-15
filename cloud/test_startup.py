"""Startup policy: changing bind/port handling must preserve these boundaries."""
import os
import unittest
from unittest.mock import patch
import server


class StartupTest(unittest.TestCase):
    def start(self, **settings):
        env = {'KAEW_DEVICE_TOKEN': 'device-test', 'KAEW_ADMIN_TOKEN': 'admin-test', **settings}
        # Stop at the socket-creation boundary: main must pass the validated settings.
        with patch.dict(os.environ, env, clear=True), patch.object(server, 'create_server', side_effect=InterruptedError) as create:
            with self.assertRaises(InterruptedError):
                server.main()
        return create.call_args.args

    def test_default_loopback_and_port(self):
        self.assertEqual(self.start()[:2], ('127.0.0.1', 8080))

    def test_public_bind_requires_explicit_flag(self):
        for host in ('0.0.0.0', '::'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                self.start(KAEW_HOST=host)

    def test_edge_https_allows_public_bind(self):
        self.assertEqual(self.start(KAEW_HOST='0.0.0.0', KAEW_TRUST_EDGE_HTTPS='1')[:2], ('0.0.0.0', 8080))

    def test_lan_flag_remains_available(self):
        self.assertEqual(self.start(KAEW_HOST='0.0.0.0', KAEW_DEV_ALLOW_INSECURE_LAN='1')[0], '0.0.0.0')

    def test_edge_flag_must_be_one(self):
        with self.assertRaises(ValueError):
            self.start(KAEW_HOST='0.0.0.0', KAEW_TRUST_EDGE_HTTPS='0')

    def test_platform_port_fallback(self):
        self.assertEqual(self.start(PORT='10000')[1], 10000)

    def test_explicit_port_wins(self):
        self.assertEqual(self.start(PORT='10000', KAEW_PORT='9000')[1], 9000)

    def test_edge_does_not_bypass_token_validation(self):
        for device, admin in (('', ''), ('same', 'same'), ('device-test', '')):
            with self.subTest(device=device, admin=admin), self.assertRaises(ValueError):
                server.create_server('0.0.0.0', 0, ':memory:', device, admin)
