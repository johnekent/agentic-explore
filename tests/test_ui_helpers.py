import unittest

from agentlab import ui_helpers


class TestUIHelpers(unittest.TestCase):
    def test_build_row_key(self):
        key = ui_helpers.build_row_key(
            source_type="url",
            url_or_path="https://example.com",
            run_id="run-1",
            content_path="workspace/docs/a.md",
        )
        self.assertEqual(key, "url|https://example.com|run-1|workspace/docs/a.md")

    def test_compute_fetch_status_prefers_fetch_status(self):
        status = ui_helpers.compute_fetch_status({"status": "success"}, {"id": "doc-1"})
        self.assertEqual(status, "fetched")

    def test_compute_fetch_status_failed(self):
        status = ui_helpers.compute_fetch_status({"status": "failed"}, None)
        self.assertEqual(status, "fetch_failed")

    def test_compute_fetch_status_passes_through_other_status(self):
        status = ui_helpers.compute_fetch_status({"status": "skipped_already_fetched"}, None)
        self.assertEqual(status, "skipped_already_fetched")

    def test_compute_fetch_status_doc_row_fallback(self):
        status = ui_helpers.compute_fetch_status(None, {"id": "doc-1"})
        self.assertEqual(status, "fetched")

    def test_compute_fetch_status_default(self):
        status = ui_helpers.compute_fetch_status(None, None)
        self.assertEqual(status, "not_fetched")

    def test_compute_summary_status_success(self):
        status = ui_helpers.compute_summary_status(
            doc_id="doc-1",
            summary_success={"doc-1"},
            summary_failed=set(),
            doc_row=None,
        )
        self.assertEqual(status, "summarized")

    def test_compute_summary_status_failed(self):
        status = ui_helpers.compute_summary_status(
            doc_id="doc-1",
            summary_success=set(),
            summary_failed={"doc-1"},
            doc_row=None,
        )
        self.assertEqual(status, "summary_failed")

    def test_compute_summary_status_doc_row_fallback(self):
        status = ui_helpers.compute_summary_status(
            doc_id=None,
            summary_success=set(),
            summary_failed=set(),
            doc_row={"summary": "Some text"},
        )
        self.assertEqual(status, "summarized")

    def test_compute_summary_status_default(self):
        status = ui_helpers.compute_summary_status(
            doc_id=None,
            summary_success=set(),
            summary_failed=set(),
            doc_row=None,
        )
        self.assertEqual(status, "not_summarized")

    def test_compute_index_status_success(self):
        status = ui_helpers.compute_index_status(
            doc_id="doc-1",
            index_success={"doc-1"},
            index_failed=set(),
        )
        self.assertEqual(status, "indexed")

    def test_compute_index_status_failed(self):
        status = ui_helpers.compute_index_status(
            doc_id="doc-1",
            index_success=set(),
            index_failed={"doc-1"},
        )
        self.assertEqual(status, "index_failed")

    def test_compute_index_status_default(self):
        status = ui_helpers.compute_index_status(
            doc_id=None,
            index_success=set(),
            index_failed=set(),
        )
        self.assertEqual(status, "not_indexed")

    def test_eligible_fetch(self):
        self.assertTrue(ui_helpers.eligible_fetch("not_fetched"))
        self.assertTrue(ui_helpers.eligible_fetch("fetch_failed"))
        self.assertFalse(ui_helpers.eligible_fetch("fetched"))

    def test_eligible_summarize(self):
        self.assertTrue(
            ui_helpers.eligible_summarize(
                "fetched",
                "not_summarized",
                "workspace/docs/a.md",
            )
        )
        self.assertFalse(
            ui_helpers.eligible_summarize(
                "not_fetched",
                "not_summarized",
                "workspace/docs/a.md",
            )
        )
        self.assertFalse(
            ui_helpers.eligible_summarize(
                "fetched",
                "not_summarized",
                "   ",
            )
        )

    def test_eligible_index(self):
        self.assertTrue(
            ui_helpers.eligible_index(
                "summarized",
                "not_indexed",
                "workspace/docs/a.md",
            )
        )
        self.assertFalse(
            ui_helpers.eligible_index(
                "not_summarized",
                "not_indexed",
                "workspace/docs/a.md",
            )
        )
        self.assertFalse(
            ui_helpers.eligible_index(
                "summarized",
                "not_indexed",
                "",
            )
        )
    
    def test_sequence_enforces_fetch_before_summarize(self):
        self.assertFalse(
            ui_helpers.eligible_summarize(
                "not_fetched",
                "not_summarized",
                "workspace/docs/a.md",
            )
        )
        self.assertFalse(
            ui_helpers.eligible_summarize(
                "fetch_failed",
                "not_summarized",
                "workspace/docs/a.md",
            )
        )
        self.assertTrue(
            ui_helpers.eligible_summarize(
                "skipped_already_fetched",
                "not_summarized",
                "workspace/docs/a.md",
            )
        )
        self.assertTrue(
            ui_helpers.eligible_summarize(
                "uploaded",
                "not_summarized",
                "workspace/docs/a.md",
            )
        )

    def test_sequence_enforces_summarize_before_index(self):
        self.assertFalse(
            ui_helpers.eligible_index(
                "not_summarized",
                "not_indexed",
                "workspace/docs/a.md",
            )
        )
        self.assertFalse(
            ui_helpers.eligible_index(
                "summary_failed",
                "not_indexed",
                "workspace/docs/a.md",
            )
        )
        self.assertTrue(
            ui_helpers.eligible_index(
                "summarized",
                "not_indexed",
                "workspace/docs/a.md",
            )
        )


if __name__ == "__main__":
    unittest.main()
