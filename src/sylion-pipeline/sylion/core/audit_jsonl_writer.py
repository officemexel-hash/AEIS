from __future__ import annotations

import logging
import threading
import time
from pathlib import Path


class AuditJsonlWriter:
    def __init__(self, path, ensure_dir: bool = True):
        self.path = Path(path)
        self.ensure_dir = ensure_dir
        self._lock = threading.Lock()

    def append(self, payload: dict) -> None:
        try:
            import json

            if self.ensure_dir:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(payload, ensure_ascii=False) + "\n"
            last_exc = None
            for _ in range(20):
                try:
                    with self._lock, self.path.open("a", encoding="utf-8") as f:
                        f.write(line)
                    return
                except IOError as exc:
                    last_exc = exc
                    time.sleep(0.005)
            if last_exc:
                raise last_exc
        except (ImportError, IOError) as exc:
            logging.warning("AuditJsonlWriter append failed for %s: %s", self.path, exc)
