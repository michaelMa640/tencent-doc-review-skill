import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.access import CommandMCPClient, DownloadFormat, TencentDocReference, UploadTarget, build_bridge_config
from tencent_doc_review.cli import main
from click.testing import CliRunner


class PhaseFCommandBridgeAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_bridge_client_round_trips_export_and_upload(self):
        bridge_script = PROJECT_ROOT / "tests" / "fixtures" / "mock_mcp_bridge.py"
        config = build_bridge_config(
            client_name="openclaw",
            executable=sys.executable,
            args_text=str(bridge_script),
            timeout_seconds=30,
        )
        client = CommandMCPClient(config)

        reference = TencentDocReference(doc_id="doc-bridge-123", title="Bridge Demo")
        export_payload = await client.export_document(reference, DownloadFormat.DOCX)

        self.assertEqual(export_payload.filename, "doc-bridge-123.docx")
        self.assertIn("Mock bridge正文第一段", export_payload.text_content)
        self.assertEqual(export_payload.metadata["bridge_client"], "openclaw")

        tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phasef-bridge-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            local_path = tmpdir / "annotated.docx"
            local_path.write_bytes(b"bridge-docx")
            upload_payload = await client.upload_document(
                local_path=local_path,
                target=UploadTarget(folder_id="folder-1", space_type="personal_space"),
                remote_filename="annotated.docx",
            )
            self.assertEqual(upload_payload.remote_file_id, "bridge-remote-file-id")
            self.assertEqual(upload_payload.metadata["target_space_type"], "personal_space")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_skill_run_uses_openclaw_bridge_configuration(self):
        bridge_script = PROJECT_ROOT / "tests" / "fixtures" / "mock_mcp_bridge.py"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "skill-run",
                "--doc-id",
                "doc-bridge-123",
                "--title",
                "Bridge Demo",
                "--target-folder-id",
                "folder-1",
                "--target-space-type",
                "personal_space",
                "--target-path",
                "/review-results",
                "--mcp-client",
                "openclaw",
                "--bridge-executable",
                sys.executable,
                "--bridge-args",
                str(bridge_script),
            ],
        )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["remote_file_id"], "bridge-remote-file-id")
        self.assertEqual(payload["target_location"]["space_type"], "personal_space")


if __name__ == "__main__":
    unittest.main()
