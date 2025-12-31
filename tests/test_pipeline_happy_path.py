import os
import tempfile
import unittest
from pathlib import Path

from agentlab.agents.planner_orchestrator import build_planner


class TestPipelineHappyPath(unittest.TestCase):
    def test_capture_idea(self):
        tmp = tempfile.TemporaryDirectory()
        os.environ["AGENTLAB_DB_PATH"] = str(Path(tmp.name) / "test.db")
        # create table
        from agentlab.db.db import connect
        con = connect(Path(os.environ["AGENTLAB_DB_PATH"]))
        con.execute("CREATE TABLE ideas(id TEXT, title TEXT)")
        con.commit()
        con.close()

        planner = build_planner()
        res = planner.run_capture_idea([{"id": "1", "title": "idea"}])
        self.assertTrue(res["ok"])
        self.assertEqual(res["inserted"], 1)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
