"""Per-run JSONL trace writer."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _default(o: Any) -> Any:
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


class Trace:
    def __init__(self, path: Path | None):
        self.path = path
        self.events: list[dict[str, Any]] = []
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = path.open("w")
        else:
            self._fh = None

    def log(self, event: str, **data: Any) -> None:
        line = json.dumps({"t": time.time(), "event": event, **data}, default=_default)
        # Keep the in-memory copy identical to the file (plain JSON types, no dataclasses).
        self.events.append(json.loads(line))
        if self._fh is not None:
            self._fh.write(line + "\n")
            self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
