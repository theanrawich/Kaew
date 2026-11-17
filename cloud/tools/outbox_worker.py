"""Single-process outbox delivery loop; failures remain queued."""
import random
import threading


class OutboxWorker:
    def __init__(self, queue, url, token, idle_seconds=1.0, max_backoff=60.0):
        self.queue, self.url, self.token = queue, url, token
        self.idle_seconds, self.max_backoff = idle_seconds, max_backoff
        self._stop = threading.Event()
        self._thread = None
        self.sent = 0
        self.failures = 0

    def start(self):
        if self._thread and self._thread.is_alive(): raise RuntimeError('worker already running')
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='kaew-outbox', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=4)

    def _run(self):
        delay = self.idle_seconds
        while not self._stop.is_set():
            try:
                pending = self.queue.count()
                sent = self.queue.flush(self.url, self.token) if pending else 0
                self.sent += sent
                if pending and self.queue.count() and not sent:
                    self.failures += 1
                    delay = min(self.max_backoff, max(self.idle_seconds, delay * 2))
                    self._stop.wait(delay * random.uniform(0.8, 1.2))
                else:
                    delay = self.idle_seconds
                    self._stop.wait(delay)
            except Exception:
                # Preserve the queue; configuration and storage errors remain visible via failures.
                self.failures += 1
                delay = min(self.max_backoff, max(self.idle_seconds, delay * 2))
                self._stop.wait(delay * random.uniform(0.8, 1.2))
