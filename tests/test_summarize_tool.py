import unittest

from agentlab.providers import llm as llm_mod
from agentlab.tools import summarize_tools


class DummyLLM:
    def __init__(self, text: str):
        self._text = text

    def complete(self, system: str, user: str, temperature: float = 0.2):
        return llm_mod.LLMResult(text=self._text, raw=None)


class TestSummarizeTool(unittest.TestCase):
    def test_summarize_document_success(self):
        original = summarize_tools.get_provider
        summarize_tools.get_provider = lambda: DummyLLM('{"title":"T","summary":"S"}')
        try:
            res = summarize_tools.summarize_document("hello world", url="https://example.com")
            self.assertTrue(res.ok)
            self.assertEqual(res.data["title"], "T")
            self.assertEqual(res.data["summary"], "S")
        finally:
            summarize_tools.get_provider = original


if __name__ == "__main__":
    unittest.main()
