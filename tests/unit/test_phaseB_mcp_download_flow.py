import sys
import unittest
import shutil
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.access import (
    DownloadFormat,
    DownloadManager,
    MCPDownloadPayload,
    TencentDocReference,
)


class _FakeMCPClient:
    async def export_document(self, reference, download_format=DownloadFormat.DOCX):
        suffix = ".docx" if download_format is DownloadFormat.DOCX else ".md"
        return MCPDownloadPayload(
            reference=reference,
            format=download_format,
            filename=f"{reference.title}{suffix}",
            content_bytes=b"fake-binary-content",
            metadata={"source": "fake-mcp"},
        )


class PhaseBMCPDownloadFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_download_manager_materializes_docx_to_temp_dir(self):
        tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phaseb-download-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            manager = DownloadManager(root_dir=tmpdir)
            reference = TencentDocReference(
                doc_id="doc-123",
                title="Example Review Document",
                folder_id="folder-1",
                space_id="space-1",
            )

            downloaded = await manager.download_via_mcp(
                _FakeMCPClient(),
                reference,
                purpose="document",
                download_format=DownloadFormat.DOCX,
            )

            self.assertTrue(downloaded.file_path.exists())
            self.assertEqual(downloaded.file_path.suffix, ".docx")
            self.assertEqual(downloaded.reference.doc_id, "doc-123")
            self.assertEqual(downloaded.metadata["source"], "fake-mcp")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_build_plan_adds_purpose_suffix_for_template_download(self):
        tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phaseb-template-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            manager = DownloadManager(root_dir=tmpdir)
            reference = TencentDocReference(doc_id="doc-123", title="Quarterly Plan")

            plan = manager.build_plan(
                reference,
                download_format=DownloadFormat.DOCX,
                purpose="template",
            )

            self.assertEqual(plan.filename, "Quarterly-Plan-template.docx")
            self.assertEqual(plan.target_dir.name, "doc-123")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_build_plan_sanitizes_invalid_filename_chars(self):
        tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phaseb-sanitize-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            manager = DownloadManager(root_dir=tmpdir)
            reference = TencentDocReference(doc_id="doc:123", title="Doc / With : Invalid * Chars")

            plan = manager.build_plan(reference, download_format=DownloadFormat.DOCX)

            self.assertEqual(plan.filename, "Doc-With-Invalid-Chars.docx")
            self.assertEqual(plan.target_dir.name, "doc-123")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
