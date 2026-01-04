import os
from pathlib import Path

from agentlab.core.paths import ensure_workspace
from agentlab.db.db import apply_migrations_from_dir, connect


def init_test_db(tmp_dir: Path) -> Path:
    ws = ensure_workspace(tmp_dir)
    db_path = ws.db_path
    os.environ["AGENTLAB_DB_PATH"] = str(db_path)
    con = connect(db_path)
    migrations_dir = Path(__file__).resolve().parents[2] / "db" / "migrations"
    apply_migrations_from_dir(con, migrations_dir)
    con.close()
    return db_path
