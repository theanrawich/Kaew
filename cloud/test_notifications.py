import json
import unittest
from notifications import TelegramProvider, MockProvider, DeliveryError


class NotificationsTest(unittest.TestCase):
    def test_telegram_adapter_sends_text_without_logging_credentials(self):
        captured=[]
        def fake(url, body):
            captured.append((url, json.loads(body)))
            return {'ok':True, 'result':{'message_id':123}}
        provider=TelegramProvider('123:token', '42', transport=fake)
        self.assertEqual(provider.send('ดื่มน้ำได้แล้ว'), '123')
        self.assertEqual(captured[0][1], {'chat_id':'42','text':'ดื่มน้ำได้แล้ว'})
        self.assertTrue(captured[0][0].endswith('/sendMessage'))
    def test_failures_are_sanitized_and_mock_is_observable(self):
        def fail(url,body): raise OSError('secret embedded in URL')
        with self.assertRaises(DeliveryError) as e: TelegramProvider('123:secret','42',transport=fail).send('hello')
        self.assertNotIn('secret',str(e.exception))
        mock=MockProvider(); mock.send('hello'); self.assertEqual(mock.messages,['hello'])


if __name__ == '__main__': unittest.main()
