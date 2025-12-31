import unittest

from agentlab.tools.local_exec import local_exec


class TestLocalExec(unittest.TestCase):
    def test_local_exec(self):
        res = local_exec(["python", "-c", "print('ok')"])
        self.assertTrue(res.ok)
        self.assertIn("ok", res.data["stdout"])


if __name__ == "__main__":
    unittest.main()
