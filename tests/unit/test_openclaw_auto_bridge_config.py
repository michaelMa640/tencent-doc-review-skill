import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import click

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.access import CommandMCPClient
from tencent_doc_review.cli import _create_skill_mcp_client


class OpenClawAutoBridgeConfigTests(unittest.TestCase):
    def _settings(self, **overrides):
        base = {
            "openclaw_mcp_bridge_executable": "",
            "openclaw_mcp_bridge_args": "",
            "claude_code_mcp_bridge_executable": "",
            "claude_code_mcp_bridge_args": "",
            "mcp_bridge_timeout": 120,
            "tencent_docs_token": "token-123",
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    @patch("tencent_doc_review.cli._detect_python_executable", return_value="python-auto")
    @patch("tencent_doc_review.cli._detect_openclaw_executable", return_value="openclaw-auto")
    def test_openclaw_client_can_autodetect_bridge_settings(self, _openclaw, _python):
        client = _create_skill_mcp_client("openclaw", self._settings())

        self.assertIsInstance(client, CommandMCPClient)
        self.assertEqual(client.config.executable, "python-auto")
        self.assertIn("--openclaw-executable", client.config.args)
        self.assertIn("openclaw-auto", client.config.args)
        self.assertTrue(client.config.args[0].endswith("openclaw_bridge.py"))
        self.assertEqual(client.config.env["TENCENT_DOCS_TOKEN"], "token-123")

    @patch("tencent_doc_review.cli._detect_python_executable", return_value="python-auto")
    @patch("tencent_doc_review.cli._detect_openclaw_executable", return_value="")
    def test_openclaw_client_raises_when_autodetect_fails(self, _openclaw, _python):
        with self.assertRaises(click.UsageError):
            _create_skill_mcp_client("openclaw", self._settings())

    def test_openclaw_client_prefers_explicit_bridge_config(self):
        client = _create_skill_mcp_client(
            "openclaw",
            self._settings(
                openclaw_mcp_bridge_executable="python-explicit",
                openclaw_mcp_bridge_args="bridge.py --openclaw-executable openclaw-explicit --agent-id main --no-local",
            ),
        )

        self.assertIsInstance(client, CommandMCPClient)
        self.assertEqual(client.config.executable, "python-explicit")
        self.assertIn("bridge.py", client.config.args)
        self.assertIn("openclaw-explicit", client.config.args)


if __name__ == "__main__":
    unittest.main()
