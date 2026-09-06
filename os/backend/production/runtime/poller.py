import os
import threading
from datetime import datetime, timezone

from production.providers import get_provider
from production.runtime.manager import get_jobs
from production.runtime.worker import ProductionRuntimeWorker


class ProductionRuntimePoller:
    """Small in-process poller for active remote Production jobs.

    Remote Pay Guide OS is currently a single-user local control plane, so a
    lightweight daemon thread is sufficient and avoids requiring an external
    queue just to finish asynchronous AI Gateway jobs. The poller only refreshes
    already-submitted jobs; it never creates or submits ProductionTasks.
    """

    def __init__(self, interval_seconds=None, worker=None):
        value = interval_seconds
        if value is None:
            value = os.getenv('PRODUCTION_POLL_INTERVAL_SECONDS') or 10
        self.interval_seconds = max(2.0, float(value))
        self.worker = worker or ProductionRuntimeWorker()
        self._stop_event = threading.Event()
        self._thread = None
        self.last_poll_at = None
        self.last_error = None
        self.poll_count = 0

    def poll_once(self):
        checked = 0
        refreshed = 0
        failures = []

        for job in get_jobs():
            if str(job.get('status') or '').strip().lower() != 'running':
                continue
            provider = get_provider(job.get('provider'))
            if provider is None or not hasattr(provider, 'poll_job'):
                continue

            checked += 1
            try:
                self.worker.poll(job)
                refreshed += 1
            except Exception as exc:
                failures.append({
                    'runtime_job_id': job.get('id'),
                    'provider': job.get('provider'),
                    'error': str(exc),
                })

        self.last_poll_at = datetime.now(timezone.utc).isoformat()
        self.poll_count += 1
        self.last_error = failures[0]['error'] if failures else None
        return {
            'checked': checked,
            'refreshed': refreshed,
            'failed': len(failures),
            'failures': failures,
            'polled_at': self.last_poll_at,
        }

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception as exc:
                self.last_error = str(exc)
            self._stop_event.wait(self.interval_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            return self.status()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name='production-runtime-poller',
            daemon=True,
        )
        self._thread.start()
        return self.status()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=min(self.interval_seconds, 2.0))
        return self.status()

    def status(self):
        return {
            'running': bool(self._thread and self._thread.is_alive()),
            'interval_seconds': self.interval_seconds,
            'last_poll_at': self.last_poll_at,
            'last_error': self.last_error,
            'poll_count': self.poll_count,
        }


runtime_poller = ProductionRuntimePoller()
