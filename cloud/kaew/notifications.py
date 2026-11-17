"""Notification providers. No external delivery is attempted without explicit configuration."""
import json
import re
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


class DeliveryError(Exception):
    pass


class MockProvider:
    def __init__(self): self.messages = []
    def send(self, text):
        self.messages.append(text)
        return str(len(self.messages))


def _post(url, body):
    req=urllib.request.Request(url, data=body, method='POST', headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=5) as response:
        return json.load(response)


class TelegramProvider:
    def __init__(self, token, chat_id, transport=_post):
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token or '') or not re.fullmatch(r'-?[0-9]+', str(chat_id or '')):
            raise ValueError('invalid Telegram configuration')
        self._token, self._chat_id, self._transport = token, str(chat_id), transport

    def send(self, text):
        if not isinstance(text,str) or not 0 < len(text) <= 4096: raise ValueError('invalid message')
        body=json.dumps({'chat_id':self._chat_id, 'text':text},ensure_ascii=False).encode('utf-8')
        try:
            response=self._transport('https://api.telegram.org/bot'+self._token+'/sendMessage',body)
            if response.get('ok') is not True or 'message_id' not in response.get('result',{}): raise ValueError()
            return str(response['result']['message_id'])
        except Exception:
            # Transport exceptions can include the credential-bearing URL.
            raise DeliveryError('Telegram delivery failed') from None
