import unittest

from agentlab.providers import llm as llm_mod
from agentlab.tools import llm_generate as llm_tool


class DummyLLM:
    def complete(self, system: str, user: str, temperature: float = 0.2):
        return llm_mod.LLMResult(text='{"ok": true}', raw=None)


class TestLlmGenerate(unittest.TestCase):
    def test_llm_generate(self):
        original = llm_tool.get_provider
        llm_tool.get_provider = lambda: DummyLLM()
        try:
            res = llm_tool.llm_generate("sys", "user")
            self.assertTrue(res.ok)
            self.assertIn("ok", res.data["text"])
        finally:
            llm_tool.get_provider = original


if __name__ == "__main__":
    unittest.main()
