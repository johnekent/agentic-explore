import json
import tempfile
import unittest
from pathlib import Path

from agentlab.db.db import connect
from agentlab.orchestrator.runtime import default_orchestrator
from agentlab.skills_runtime.operations_skills import FetchUrls
from agentlab.tools import web_tools
from agentlab.tools.types import ToolResult
from tests.helpers.db import init_test_db


class TestFetchUrlsSkill(unittest.TestCase):
    def test_fetch_urls_no_summary(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp_path = Path(tmp.name)
        db_path = init_test_db(tmp_path)

        original = web_tools.fetch_url
        web_tools.fetch_url = lambda url, timeout_s=30, headers=None: ToolResult.success(
            {"text": "Hello world"}
        )
        try:
            orch = default_orchestrator()
            skill = FetchUrls()
            result = skill.run(
                orch,
                urls=["https://example.com"],
                workspace=tmp_path,
                regenerate_summary=False,
                agent_name="test",
                agent_type="unit",
            )
            self.assertEqual(result["fetched"], 1)
        finally:
            web_tools.fetch_url = original

        con = connect(db_path)
        row = con.execute(
            "SELECT metadata_json FROM item_processing WHERE stage = 'fetch' AND status = 'success' LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(row)
        meta = json.loads(row["metadata_json"] or "{}")
        doc_path = Path(meta.get("path", ""))
        self.assertTrue(doc_path and doc_path.exists())
        content = doc_path.read_text(encoding="utf-8")
        from agentlab.core.frontmatter import parse_md_with_frontmatter
        md = parse_md_with_frontmatter(content)
        self.assertIn("title", md.frontmatter)
        self.assertIn("summary", md.frontmatter)
        self.assertEqual(str(md.frontmatter.get("title") or "").strip(), "")
        self.assertEqual(str(md.frontmatter.get("summary") or "").strip(), "")
        summary_row = con.execute(
            "SELECT 1 FROM item_processing WHERE stage = 'summary' AND status = 'success' LIMIT 1"
        ).fetchone()
        self.assertIsNone(summary_row)
        con.close()

        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
