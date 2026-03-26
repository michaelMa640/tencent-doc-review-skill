import sys
import shutil
import uuid
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.access import MCPUploadPayload, UploadManager, UploadTarget


class _FakeUploadClient:
    async def upload_document(self, local_path: Path, target: UploadTarget, remote_filename: str):
        return MCPUploadPayload(
            target=target,
            uploaded_name=remote_filename,
            remote_file_id="remote-file-123",
            remote_url="https://docs.qq.com/mock/remote-file-123",
            metadata={"source": "fake-mcp-upload"},
        )


class PhaseDUploadManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_manager_returns_normalized_upload_result(self):
        tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phased-upload-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            local_path = tmpdir / "annotated.docx"
            local_path.write_bytes(b"fake-docx")

            target = UploadTarget(
                folder_id="folder-123",
                space_id="space-456",
                path_hint="/审核结果/2026",
                display_name="审核结果",
            )

            result = await UploadManager().upload_via_mcp(
                client=_FakeUploadClient(),
                local_path=local_path,
                target=target,
                remote_filename="reviewed.docx",
            )

            self.assertEqual(result.remote_file_id, "remote-file-123")
            self.assertEqual(result.remote_filename, "reviewed.docx")
            self.assertEqual(result.target.folder_id, "folder-123")
            self.assertEqual(result.metadata["source"], "fake-mcp-upload")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_build_plan_defaults_to_local_filename(self):
        tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phased-plan-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            local_path = tmpdir / "annotated.docx"
            local_path.write_bytes(b"fake-docx")

            target = UploadTarget(folder_id="folder-123", space_id="space-456")
            plan = UploadManager().build_plan(local_path=local_path, target=target)

            self.assertEqual(plan.remote_filename, "annotated.docx")
            self.assertFalse(plan.overwrite)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
