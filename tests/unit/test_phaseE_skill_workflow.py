import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.access import (
    DownloadFormat,
    DownloadedDocument,
    MCPDownloadPayload,
    MCPUploadPayload,
    TencentDocReference,
    UploadTarget,
)
from tencent_doc_review.cli import main
from tencent_doc_review.analyzer.document_analyzer import AnalysisResult, AnalysisType
from tencent_doc_review.analyzer.fact_checker import ClaimType, FactCheckResult, VerificationStatus
from tencent_doc_review.document.word_parser import ParagraphNode, SentenceNode
from tencent_doc_review.domain import ReviewIssue, ReviewIssueType, ReviewSeverity
from tencent_doc_review.skill import SkillRequest
from tencent_doc_review.workflows import SkillPipeline


class _FakeSkillClient:
    def __init__(self) -> None:
        self.last_reference = None

    async def export_document(self, reference, download_format=DownloadFormat.DOCX):
        self.last_reference = reference
        return MCPDownloadPayload(
            reference=reference,
            format=download_format,
            filename="source.docx",
            text_content="Skill pipeline example content.",
            metadata={"source": "fake-skill-client", "used_text_fallback": True},
        )

    async def upload_document(self, local_path, target, remote_filename):
        return MCPUploadPayload(
            target=target,
            uploaded_name=remote_filename,
            remote_file_id="remote-123",
            remote_url="https://docs.qq.com/mock/remote-123",
            metadata={"source": "fake-skill-client"},
        )


class PhaseESkillWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def test_stable_local_filename_uses_source_title(self):
        pipeline = SkillPipeline()
        tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phasee-rename-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            original_path = tmpdir / "run-20260329-1600-michael.docx"
            original_path.write_bytes(b"demo")
            materialized = pipeline._ensure_stable_local_filename(
                downloaded=DownloadedDocument(
                    reference=TencentDocReference(doc_id="doc-123", title="副本-蝉镜产品调研报告-michael"),
                    file_path=original_path,
                    download_format=DownloadFormat.DOCX,
                    filename=original_path.name,
                    purpose="document",
                    metadata={},
                ),
                request=SkillRequest(
                    source_document=TencentDocReference(doc_id="doc-123", title="副本-蝉镜产品调研报告-michael"),
                    target_location=UploadTarget(folder_id="folder-456", space_type="personal_space", path_hint="/review-results"),
                ),
            )

            self.assertTrue(materialized.file_path.name.startswith("副本-蝉镜产品调研报告-michael"))
            self.assertTrue(materialized.file_path.exists())
            self.assertFalse(original_path.exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def test_skill_pipeline_returns_unified_skill_response(self):
        tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phasee-skill-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            client = _FakeSkillClient()
            request = SkillRequest(
                source_document=TencentDocReference(doc_id="doc-123", title="Skill Demo"),
                target_location=UploadTarget(
                    folder_id="folder-456",
                    space_type="personal_space",
                    path_hint="/review-results",
                ),
                download_directory=str(tmpdir),
                llm_provider="mock",
            )

            response = await SkillPipeline().run(client, request)

            self.assertTrue(response.success)
            self.assertEqual(response.remote_file_id, "remote-123")
            self.assertTrue(response.annotated_word_path.endswith("-annotated.docx"))
            self.assertEqual(response.metadata["uploaded_local_word_path"], response.annotated_word_path)
            self.assertEqual(response.target_location.folder_id, "folder-456")
            self.assertTrue(response.metadata["used_text_fallback"])
            self.assertGreater(response.metadata["annotation_count"], 0)
            self.assertIn("markdown", response.generated_reports)
            self.assertEqual(client.last_reference.metadata["preferred_download_dir"], str(tmpdir))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_skill_info_prints_runtime_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["skill-info"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.output)
        self.assertIn("platform", payload)
        self.assertIn("temp_root", payload)
        self.assertIn("default_mcp_client", payload)

    def test_cli_skill_run_prints_response(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "skill-run",
                "--doc-id",
                "doc-123",
                "--title",
                "Skill Demo",
                "--target-folder-id",
                "folder-456",
                "--target-path",
                "/review-results",
                "--provider",
                "mock",
            ],
        )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["remote_file_id"], "mock-remote-file-id")

    def test_resolve_paragraph_index_uses_visible_paragraph_mapping(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="标题", is_heading=True, heading_level=1),
            ParagraphNode(index=1, text=""),
            ParagraphNode(index=2, text="第一段正文"),
            ParagraphNode(index=3, text=""),
            ParagraphNode(index=4, text="第二段正文"),
        ]
        issue = ReviewIssue(
            issue_type=ReviewIssueType.FACT,
            severity=ReviewSeverity.MEDIUM,
            title="事实待核实",
            description="desc",
            source_excerpt="第二段正文",
            location={"paragraph_index": 2},
        )

        resolved = pipeline._resolve_paragraph_index(paragraphs, issue)

        self.assertEqual(resolved, 4)

    def test_substring_match_prefers_body_paragraph_over_heading_fallback(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="文章标题", is_heading=True, heading_level=1),
            ParagraphNode(index=1, text="第一段正文，介绍产品背景。"),
            ParagraphNode(index=2, text="第二段正文，说明该产品支持中英文多语种。"),
        ]
        issue = ReviewIssue(
            issue_type=ReviewIssueType.FACT,
            severity=ReviewSeverity.MEDIUM,
            title="事实待核实",
            description="支持中英文多语种",
            suggestion="该内容需要复查。",
            source_excerpt="支持中英文多语种",
            location={"paragraph_index": 0},
        )

        annotation = pipeline._to_word_annotation(paragraphs, [], issue)

        self.assertEqual(annotation.paragraph_index, 2)
        self.assertNotIn("render_mode", annotation.metadata)

    def test_issue_with_source_excerpt_but_no_reliable_anchor_goes_to_summary_block(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="文章标题", is_heading=True, heading_level=1),
            ParagraphNode(index=1, text="第一段正文，介绍产品背景。"),
            ParagraphNode(index=2, text="第二段正文，说明价格策略。"),
        ]
        issue = ReviewIssue(
            issue_type=ReviewIssueType.FACT,
            severity=ReviewSeverity.MEDIUM,
            title="事实待核实",
            description="一个没有可靠锚点的判断",
            suggestion="该内容需要复查。",
            source_excerpt="支持中英文多语种",
            location={"paragraph_index": 2},
        )

        annotation = pipeline._to_word_annotation(paragraphs, [], issue)

        self.assertEqual(annotation.paragraph_index, 2)
        self.assertEqual(annotation.metadata.get("render_mode"), "summary_block")
        self.assertEqual(annotation.metadata.get("anchor_reason"), "preferred_approximate")

    def test_source_excerpt_without_anchor_uses_summary_block_not_last_paragraph(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="文章标题", is_heading=True, heading_level=1),
            ParagraphNode(index=1, text="第一段正文，介绍产品背景。"),
            ParagraphNode(index=2, text="第二段正文，说明价格策略。"),
        ]
        issue = ReviewIssue(
            issue_type=ReviewIssueType.FACT,
            severity=ReviewSeverity.MEDIUM,
            title="事实待核实",
            description="一个没有可靠锚点的判断",
            suggestion="该内容需要复查。",
            source_excerpt="支持中英文多语种",
            location={"paragraph_index": 0},
        )

        annotation = pipeline._to_word_annotation(paragraphs, [], issue)

        self.assertEqual(annotation.metadata.get("render_mode"), "summary_block")
        self.assertIn(annotation.paragraph_index, {1, 2})

    def test_fuzzy_sentence_match_recovers_nearby_original_sentence(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="Document Title", is_heading=True, heading_level=1),
            ParagraphNode(
                index=1,
                text="Video avatar: only 15 seconds of source footage is needed to recreate the user's appearance and voice 1:1.",
            ),
            ParagraphNode(index=2, text="Another paragraph about pricing."),
        ]
        sentences = [
            SentenceNode(index=0, paragraph_index=0, text="Document Title", is_heading=True),
            SentenceNode(
                index=1,
                paragraph_index=1,
                text="Video avatar: only 15 seconds of source footage is needed to recreate the user's appearance and voice 1:1.",
                paragraph_text=paragraphs[1].text,
            ),
            SentenceNode(index=2, paragraph_index=2, text="Another paragraph about pricing.", paragraph_text=paragraphs[2].text),
        ]
        issue = ReviewIssue(
            issue_type=ReviewIssueType.FACT,
            severity=ReviewSeverity.MEDIUM,
            title="Fact Needs Review",
            description="Video avatar function only 15 seconds of source footage is needed to recreate the user's appearance and voice 1:1.",
            suggestion="Please verify this claim.",
            source_excerpt="Video avatar function only 15 seconds of source footage is needed to recreate the user's appearance and voice 1:1.",
            location={"paragraph_index": 0},
        )

        annotation = pipeline._to_word_annotation(paragraphs, sentences, issue)

        self.assertEqual(annotation.paragraph_index, 1)
        self.assertNotIn("render_mode", annotation.metadata)

    def test_word_comment_formats_sources_without_python_repr(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="标题", is_heading=True, heading_level=1),
            ParagraphNode(index=1, text="视频生成数字人：仅需15秒原始视频即可1:1复刻用户的形象与声音。"),
        ]
        issue = ReviewIssue(
            issue_type=ReviewIssueType.FACT,
            severity=ReviewSeverity.MEDIUM,
            title="事实待核实",
            description="视频生成数字人：仅需15秒原始视频即可1:1复刻用户的形象与声音。",
            suggestion="检索到的网络信息未能直接证实该表述，建议依据下列来源核对后再保留。",
            source_excerpt="视频生成数字人：仅需15秒原始视频即可1:1复刻用户的形象与声音。",
            location={"paragraph_index": 1},
            metadata={
                "sources": [
                    {"title": "蝉镜数字人帮助文档", "url": "https://example.com/help"},
                    {"title": "京东健康官网/蝉镜产品页面", "url": ""},
                ]
            },
        )

        annotation = pipeline._to_word_annotation(paragraphs, [], issue)

        self.assertIn("问题：视频生成数字人", annotation.comment)
        self.assertIn("建议：检索到的网络信息未能直接证实该表述，建议依据下列来源核对后再保留。", annotation.comment)
        self.assertIn("1. 蝉镜数字人帮助文档 - https://example.com/help", annotation.comment)
        self.assertIn("2. 京东健康官网/蝉镜产品页面", annotation.comment)
        self.assertNotIn("[{'title':", annotation.comment)

    def test_word_comment_includes_search_trace(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="标题", is_heading=True, heading_level=1),
            ParagraphNode(index=1, text="视频生成数字人：仅需15秒原始视频即可1:1复刻用户的形象与声音。"),
        ]
        issue = ReviewIssue(
            issue_type=ReviewIssueType.FACT,
            severity=ReviewSeverity.MEDIUM,
            title="事实待核实",
            description="视频生成数字人：仅需15秒原始视频即可1:1复刻用户的形象与声音。",
            suggestion="检索到的网络信息未能直接证实该表述，建议依据下列来源核对后再保留。",
            source_excerpt="视频生成数字人：仅需15秒原始视频即可1:1复刻用户的形象与声音。",
            location={"paragraph_index": 1},
            metadata={"search_trace": {"performed": True, "provider": "tavily", "raw_count": 5, "filtered_count": 2}},
        )

        annotation = pipeline._to_word_annotation(paragraphs, [], issue)

        self.assertIn("检索痕迹：", annotation.comment)
        self.assertIn("已联网检索：tavily，候选 5 条，采纳 2 条", annotation.comment)

    def test_sentence_level_anchor_prefers_original_sentence_mapping(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="文章标题", is_heading=True, heading_level=1),
            ParagraphNode(index=1, text="第一句说明背景。第二句说明该产品支持中英文多语种。"),
        ]
        sentences = [
            SentenceNode(index=0, paragraph_index=0, text="文章标题", is_heading=True),
            SentenceNode(index=1, paragraph_index=1, text="第一句说明背景。", paragraph_text=paragraphs[1].text),
            SentenceNode(index=2, paragraph_index=1, text="第二句说明该产品支持中英文多语种。", paragraph_text=paragraphs[1].text),
        ]
        issue = ReviewIssue(
            issue_type=ReviewIssueType.FACT,
            severity=ReviewSeverity.MEDIUM,
            title="事实待核实",
            description="支持中英文多语种",
            suggestion="该内容需要复查。",
            source_excerpt="第二句说明该产品支持中英文多语种。",
            location={"paragraph_index": 0},
        )

        annotation = pipeline._to_word_annotation(paragraphs, sentences, issue)

        self.assertEqual(annotation.paragraph_index, 1)
        self.assertNotIn("render_mode", annotation.metadata)

    def test_render_document_text_keeps_original_heading_text(self):
        pipeline = SkillPipeline()
        paragraphs = [
            ParagraphNode(index=0, text="一、产品概述", is_heading=True, heading_level=1),
            ParagraphNode(index=1, text="这是正文第一段。"),
        ]

        rendered = pipeline._render_document_text(paragraphs)

        self.assertEqual(rendered, "一、产品概述\n\n这是正文第一段。")

    def test_build_word_annotations_includes_runtime_and_fact_detail_summary(self):
        pipeline = SkillPipeline()
        paragraphs = [ParagraphNode(index=0, text="标题", is_heading=True, heading_level=1)]
        sentences: list[SentenceNode] = []
        review_result = AnalysisResult(
            analysis_type=AnalysisType.FULL,
            timestamp="2026-03-29T10:00:00",
            fact_check_results=[
                FactCheckResult(
                    original_text="生成的视频清晰度可达4K。",
                    claim_type=ClaimType.DATA,
                    claim_content="生成的视频清晰度可达4K。",
                    verification_status=VerificationStatus.UNVERIFIED,
                    confidence=0.6,
                    suggestion="检索到的网络信息未能直接证实该表述，建议依据下列来源核对后再保留。",
                    sources=[
                        {
                            "title": "蝉镜帮助中心",
                            "url": "https://example.com/help",
                            "snippet": "帮助中心提到支持高清导出，但未明确写 4K。",
                        }
                    ],
                    search_trace={"performed": True, "provider": "tavily", "raw_count": 5, "filtered_count": 1},
                )
            ],
            review_issues=[],
        )
        request = SkillRequest(
            source_document=TencentDocReference(doc_id="doc-123", title="Skill Demo"),
            target_location=UploadTarget(folder_id="folder-456", space_type="personal_space", path_hint="/review-results"),
            llm_provider="deepseek",
        )

        annotations = pipeline._build_word_annotations(paragraphs, sentences, review_result, request)

        titles = [item.title for item in annotations]
        self.assertIn("审核运行情况", titles)
        self.assertIn("事实核查详细情况", titles)
        fact_detail = next(item for item in annotations if item.title == "事实核查详细情况")
        self.assertEqual(fact_detail.metadata.get("render_mode"), "summary_block")
        self.assertIn("原文：生成的视频清晰度可达4K。", fact_detail.comment)
        self.assertIn("https://example.com/help", fact_detail.comment)
        self.assertIn("搜索源原文：帮助中心提到支持高清导出，但未明确写 4K。", fact_detail.comment)
        self.assertNotIn("1. 原文：", fact_detail.comment)
        self.assertIn("来源1：蝉镜帮助中心 - https://example.com/help", fact_detail.comment)


if __name__ == "__main__":
    unittest.main()
