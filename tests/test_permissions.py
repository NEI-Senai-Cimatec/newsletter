# tests/test_permissions.py
import json

from core.audit import log_event
from core.permissions import can


def test_basic_cannot_export_but_admin_can():
    assert can("basico", "view") is True
    assert can("basico", "export") is False
    assert can("premium", "export") is True
    assert can("admin", "manage_accounts") is True
    assert can("premium", "manage_accounts") is False


def test_audit_appends_json_line(tmp_path):
    log = tmp_path / "audit.log"
    record = log_event("admin", "edit_weights", "35/35/15/15", log_path=log)
    assert record["user"] == "admin"
    assert json.loads(log.read_text(encoding="utf-8").strip())["action"] == "edit_weights"
