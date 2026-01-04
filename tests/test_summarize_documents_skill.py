import os
import tempfile
import unittest
from pathlib import Path

from agentlab.core.frontmatter import dump_md_with_frontmatter
from agentlab.db.db import connect
from agentlab.orchestrator.runtime import default_orchestrator
from agentlab.skills_runtime.operations_skills import SummarizeDocuments
from agentlab.tools import summarize_tools
from tests.helpers.db import init_test_db


class DummyLLM:
    def complete(self, system: str, user: str, temperature: float = 0.2):
        return type("LLMResult", (), {"text": '{"title":"Title","summary":"Summary"}', "raw": None})()


class TestSummarizeDocumentsSkill(unittest.TestCase):
    def test_summarize_documents_updates_db_and_logs(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp_path = Path(tmp.name)
        db_path = init_test_db(tmp_path)

        doc_id = "doc-1"
        doc_path = tmp_path / "doc.md"
        content = dump_md_with_frontmatter(
            {"id": doc_id, "type": "document", "title": "", "summary": "", "url": "https://example.com"},
            "# Content\n\nHello world\n",
        )
        doc_path.write_text(content, encoding="utf-8")

        con = connect(db_path)
        con.execute(
            "INSERT INTO documents(id, title, url, retrieved_at, summary, content_path) VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, "", "https://example.com", "2025-01-01", "", str(doc_path)),
        )
        con.commit()
        con.close()

        original = summarize_tools.get_provider
        summarize_tools.get_provider = lambda: DummyLLM()
        try:
            orch = default_orchestrator()
            skill = SummarizeDocuments()
            result = skill.run(
                orch,
                doc_paths=[str(doc_path)],
                workspace=tmp_path,
                agent_name="test",
                agent_type="unit",
            )
            self.assertEqual(result["summarized"], 1)
        finally:
            summarize_tools.get_provider = original

        con = connect(db_path)
        row = con.execute("SELECT title, summary FROM documents WHERE id = ?", (doc_id,)).fetchone()
        self.assertEqual(row["title"], "Title")
        self.assertEqual(row["summary"], "Summary")
        log = con.execute(
            "SELECT status FROM item_processing WHERE item_id = ? AND stage = 'summary' ORDER BY started_at DESC LIMIT 1",
            (doc_id,),
        ).fetchone()
        con.close()
        self.assertIsNotNone(log)
        self.assertEqual(log["status"], "success")

        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
