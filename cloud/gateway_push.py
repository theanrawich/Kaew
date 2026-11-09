"""Simulated gateway adapter: persist telemetry before attempting delivery."""
import json
import os
import sys
from pathlib import Path
from outbox import Outbox


def main():
    url = os.environ.get('KAEW_CLOUD_URL', 'http://127.0.0.1:8080')
    token = os.environ.get('KAEW_DEVICE_TOKEN', '')
    path = os.environ.get('KAEW_OUTBOX_PATH', str(Path(__file__).resolve().parent / 'outbox.sqlite3'))
    queue = Outbox(path)
    if '--flush' not in sys.argv:
        raw = sys.stdin.read(4097)
        if len(raw) > 4096: raise ValueError('sample too large')
        queue.enqueue(json.loads(raw))
    sent = queue.flush(url, token)
    remaining = queue.count()
    print('outbox sent=%d remaining=%d' % (sent, remaining))
    return 0 if remaining == 0 else 1


if __name__ == '__main__': sys.exit(main())
