from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_trace(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
