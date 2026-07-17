from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ScanJob:
    scan_id: str
    provider: str


class InProcessScanQueue:
    """Small background queue for local demo and tests.

    This keeps the service contract close to a real worker setup: API creates a
    pending scan, the worker owns execution and status transitions. Production
    can replace this with Redis/Celery/RQ without changing the API shape.
    """

    def __init__(self, handler: Callable[[ScanJob], None]) -> None:
        self._handler = handler
        self._jobs: queue.Queue[ScanJob | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="soloops-scan-worker", daemon=True)
        self._thread.start()

    def enqueue(self, job: ScanJob) -> None:
        self._jobs.put(job)

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                self._jobs.task_done()
                return
            try:
                self._handler(job)
            finally:
                self._jobs.task_done()
