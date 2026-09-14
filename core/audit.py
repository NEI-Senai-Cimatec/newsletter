"""Local JSON-lines audit log in user-space."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

AUDIT_FILE: Path = Path.home() / ".newsletter_tool" / "audit.log"


def log_event(user: str, action: str, detail: str = "",
              log_path: Path | str | None = None) -> dict:
    record = {"ts": datetime.now(timezone.utc).isoformat(),
              "user": user, "action": action, "detail": detail}
    target = Path(log_path) if log_path is not None else AUDIT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
