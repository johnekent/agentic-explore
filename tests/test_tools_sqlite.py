import os
import tempfile
import unittest
from pathlib import Path

from agentlab.tools.sqlite_tools import persist_rows, query_rows


class TestSqliteTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        os.environ["AGENTLAB_DB_PATH"] = str(self.db_path)
        # create table
        from agentlab.db.db import connect
        con = connect(self.db_path)
        con.execute("CREATE TABLE items(id TEXT, name TEXT)")
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_persist_and_query(self):
        res = persist_rows("items", [{"id": "1", "name": "a"}])
        self.assertTrue(res.ok)
        res2 = query_rows("SELECT * FROM items")
        self.assertTrue(res2.ok)
        self.assertEqual(len(res2.data["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
