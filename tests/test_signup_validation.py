# tests/test_signup_validation.py
"""Signup validation + admin helper (final fix wave I1/I2).

Tmp-path only: never touches the real ``~/.newsletter_tool/``.
"""
import pytest

from core import database


def _db(tmp_path):
    return tmp_path / "users.db"


def test_empty_username_rejected(tmp_path):
    with pytest.raises(ValueError):
        database.create_user(_db(tmp_path), "", "Nome", "QuIIN",
                             True, "basico", "senha123")


def test_blank_username_rejected(tmp_path):
    with pytest.raises(ValueError):
        database.create_user(_db(tmp_path), "   ", "Nome", "QuIIN",
                             True, "basico", "senha123")


def test_empty_password_rejected(tmp_path):
    with pytest.raises(ValueError):
        database.create_user(_db(tmp_path), "usuario1", "Nome", "QuIIN",
                             True, "basico", "")


def test_duplicate_still_valueerror(tmp_path):
    db = _db(tmp_path)
    database.create_user(db, "dup", "Dup", "QuIIN", True, "basico", "pw1")
    with pytest.raises(ValueError):
        database.create_user(db, "dup", "Dup 2", "QuIIN", True, "basico", "pw2")


def test_is_admin_user(tmp_path):
    db = _db(tmp_path)
    database.create_user(db, "adm", "Adm", "QuIIN", True, "admin", "pw")
    database.create_user(db, "bas", "Bas", "QuIIN", True, "basico", "pw")
    assert database.is_admin_user(db, "adm") is True
    assert database.is_admin_user(db, "bas") is False
    assert database.is_admin_user(db, "fantasma") is False
    assert database.is_admin_user(db, "") is False
