# tests/test_profile_update.py
import pytest

from core import database


def test_update_profile_roundtrip(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw-admin")
    database.update_profile(db, "admin", "  QuIIN Nova  ", "  Nova Org  ")
    user = database.authenticate(db, "admin", "pw-admin")
    assert user is not None
    assert user["name"] == "QuIIN Nova"
    assert user["org"] == "Nova Org"
    users = database.list_users(db)
    assert any(u["username"] == "admin" and u["name"] == "QuIIN Nova"
               and u["org"] == "Nova Org" for u in users)


def test_update_profile_unknown_username(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw-admin")
    with pytest.raises(ValueError):
        database.update_profile(db, "ghost", "Nome", "Org")


def test_update_profile_blank_name(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw-admin")
    with pytest.raises(ValueError):
        database.update_profile(db, "admin", "   ", "Org")
