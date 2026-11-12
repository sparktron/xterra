import sqlite3

import pytest

from xw import db


def test_new_and_unversioned_databases_are_adopted_without_data_loss(tmp_path):
    path = tmp_path / "legacy.sqlite"
    conn = db.connect(path)
    conn.execute("INSERT INTO sources(id, name) VALUES('test', 'preserved')")
    conn.execute("DROP TABLE schema_version")
    conn.commit()
    conn.close()

    conn = db.connect(path)
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 1
    assert conn.execute("SELECT name FROM sources WHERE id='test'").fetchone()[0] == 'preserved'
    conn.close()
    conn = db.connect(path)
    assert conn.execute("SELECT count(*) FROM schema_version").fetchone()[0] == 1
    conn.close()


def test_failed_migration_rolls_back_and_newer_schema_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "db.sqlite"
    conn = db.connect(path)
    conn.close()
    monkeypatch.setattr(db, "MIGRATIONS", (db.SCHEMA, "CREATE TABLE transient(id); invalid SQL;"))
    with pytest.raises(sqlite3.OperationalError):
        db.connect(path)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 1
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='transient'").fetchone() is None
    conn.execute("UPDATE schema_version SET version=99")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="unsupported database schema version"):
        db.connect(path)
