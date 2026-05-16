from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class JsonlLineReader:
    def __init__(self, path, skip_invalid=True):
        self.path = Path(path)
        self.skip_invalid = skip_invalid

    def __iter__(self):
        with self.path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    if not self.skip_invalid:
                        raise
                    log.warning("Skipping invalid JSONL line %s in %s", lineno, self.path)
