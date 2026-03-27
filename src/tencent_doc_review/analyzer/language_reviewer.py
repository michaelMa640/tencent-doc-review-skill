"""Sentence-level language review with retry and heuristic fallback."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from ..domain.review_models import ReviewIssue, ReviewIssueType, ReviewSeverity
from ..llm.base import LLMClient
from ..llm.structured_output import extract_json_payload


class LanguageReviewer:
    """Detect sentence-level Chinese and English language issues."""

    def __init__(self, llm_client: LLMClient, config: Optional[Dict[str, Any]] = None) -> None:
        self.llm = llm_client
        self.config = config or {}
        self.timeout_seconds = float(self.config.get("timeout_seconds", 45))
        self.max_retries = int(self.config.get("max_retries", 2))
        self.retry_delay_seconds = float(self.config.get("retry_delay_seconds", 1))
        self.temperature = float(self.config.get("temperature", 0.1))

    async def review(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[ReviewIssue]:
        if not text or not text.strip():
            return []

        llm_error: Optional[Exception] = None
        try:
            response = await self._analyze_with_retry(
                self._build_prompt(text, context or {}),
                analysis_type="general",
            )
            payload = self._extract_json_payload(response.content)
            issues = self._parse_payload(payload, text)
            if issues:
                return issues
        except Exception as exc:  # pragma: no cover - provider/network failures covered by fallback tests
            llm_error = exc
            logger.warning("LanguageReviewer LLM review failed: {}", exc)

        issues = self._heuristic_review(text)
        if llm_error and issues:
            for issue in issues:
                issue.metadata.setdefault("fallback_reason", str(llm_error))
        return issues

    async def _analyze_with_retry(self, prompt: str, analysis_type: str) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self.llm.analyze(
                        prompt,
                        analysis_type=analysis_type,
                        temperature=self.temperature,
                    ),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_delay_seconds)
        assert last_error is not None
        raise last_error

    def _build_prompt(self, text: str, context: Dict[str, Any]) -> str:
        return (
            "You are reviewing language issues in a Chinese product research report.\n"
            "The document may contain both Chinese and English.\n"
            "Only mark issues that belong to these categories: Chinese grammar, typo, unclear wording, colloquial tone, "
            "English spelling mistake, wrong word choice, or severe grammar mistake.\n"
            "Return exactly one JSON object and nothing else. Do not use markdown code fences.\n"
            'Schema: {"issues":[{"sentence":"原文句子","title":"中文标题","description":"中文说明","suggestion":"中文建议","severity":"low|medium|high"}]}\n'
            "If there are no issues, return {\"issues\":[]}.\n"
            "Each issue must point to one exact sentence from the source text.\n"
            f"Context: {json.dumps(context, ensure_ascii=False)}\n\nText:\n{text}"
        )

    def _extract_json_payload(self, content: str) -> Any:
        return extract_json_payload(content)

    def _parse_payload(self, payload: Any, full_text: str) -> List[ReviewIssue]:
        if not isinstance(payload, dict):
            return []
        items = payload.get("issues")
        if not isinstance(items, list):
            return []

        issues: List[ReviewIssue] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            sentence = str(item.get("sentence") or item.get("source_excerpt") or "").strip()
            description = str(item.get("description") or "").strip()
            if not sentence or not description or self._is_heading_like(sentence):
                continue
            issues.append(
                ReviewIssue(
                    issue_type=ReviewIssueType.LANGUAGE,
                    severity=self._parse_severity(item.get("severity")),
                    title=str(item.get("title") or "语言表达问题").strip(),
                    description=description,
                    suggestion=str(item.get("suggestion") or "").strip(),
                    source_excerpt=sentence,
                    location=self._locate_excerpt(full_text, sentence),
                    confidence=0.75,
                    metadata={"source": "llm"},
                )
            )
        return issues

    def _heuristic_review(self, text: str) -> List[ReviewIssue]:
        issues: List[ReviewIssue] = []
        for sentence in self._split_sentences(text):
            if self._is_heading_like(sentence):
                continue

            if self._is_english_dominant(sentence):
                issues.extend(self._review_english_sentence(text, sentence))
                continue

            matchers = [
                (
                    r"(大差不差|还行|挺好|特别拉满|很炸裂)",
                    "语言表达问题",
                    "句子存在口语化表达，不适合正式调研报告语体。",
                    "建议改为更客观、书面的表达。",
                    ReviewSeverity.MEDIUM,
                ),
                (
                    r"(然后|接着|然后呢).{0,8}(然后|接着)",
                    "语言衔接问题",
                    "连接词重复，影响阅读流畅度。",
                    "建议合并重复连接词，简化句式。",
                    ReviewSeverity.LOW,
                ),
                (
                    r"(非常非常|很多很多|特别特别)",
                    "表达冗余问题",
                    "存在重复修饰，表达不够凝练。",
                    "建议删去重复修饰语，保留核心判断。",
                    ReviewSeverity.LOW,
                ),
            ]
            for pattern, title, description, suggestion, severity in matchers:
                if re.search(pattern, sentence, re.IGNORECASE):
                    issues.append(
                        ReviewIssue(
                            issue_type=ReviewIssueType.LANGUAGE,
                            severity=severity,
                            title=title,
                            description=description,
                            suggestion=suggestion,
                            source_excerpt=sentence,
                            location=self._locate_excerpt(text, sentence),
                            confidence=0.55,
                            metadata={"source": "heuristic"},
                        )
                    )
                    break
        return issues

    def _review_english_sentence(self, full_text: str, sentence: str) -> List[ReviewIssue]:
        issues: List[ReviewIssue] = []
        spelling_map = {
            "seperate": "separate",
            "enviroment": "environment",
            "recieve": "receive",
            "occured": "occurred",
            "definately": "definitely",
            "acommodate": "accommodate",
            "compatable": "compatible",
        }
        lowered = sentence.lower()
        for wrong, correct in spelling_map.items():
            if wrong in lowered:
                issues.append(
                    self._build_language_issue(
                        full_text,
                        sentence,
                        "英文拼写问题",
                        f"句子中存在英文拼写错误：`{wrong}`。",
                        f"建议将 `{wrong}` 改为 `{correct}`。",
                        ReviewSeverity.MEDIUM,
                    )
                )
                return issues

        grammar_patterns = [
            (
                r"\b(this|that|it|feature|product|tool)\s+are\b",
                "英文语法问题",
                "存在主谓不一致，单数主语后不应使用 `are`。",
                "建议改为 `is`，并检查整句主谓一致。",
            ),
            (
                r"\bthese\s+\w{2,}(?<!s)\b",
                "英文语法问题",
                "`these` 后的名词看起来仍是单数形式。",
                "建议检查名词单复数是否一致。",
            ),
            (
                r"\bmore\s+(easier|better|worse|faster)\b",
                "英文用词问题",
                "存在重复比较级用法。",
                "建议删除 `more` 或重写比较结构。",
            ),
        ]
        for pattern, title, description, suggestion in grammar_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                issues.append(
                    self._build_language_issue(
                        full_text,
                        sentence,
                        title,
                        description,
                        suggestion,
                        ReviewSeverity.MEDIUM,
                    )
                )
                break
        if not issues and re.search(r"(^|[\s(])i([\s,.;:!?)]|$)", sentence):
            issues.append(
                self._build_language_issue(
                    full_text,
                    sentence,
                    "英文语法问题",
                    "英文第一人称代词 `I` 应大写。",
                    "建议将小写 `i` 改为大写 `I`。",
                    ReviewSeverity.MEDIUM,
                )
            )
        return issues

    def _build_language_issue(
        self,
        full_text: str,
        sentence: str,
        title: str,
        description: str,
        suggestion: str,
        severity: ReviewSeverity,
    ) -> ReviewIssue:
        return ReviewIssue(
            issue_type=ReviewIssueType.LANGUAGE,
            severity=severity,
            title=title,
            description=description,
            suggestion=suggestion,
            source_excerpt=sentence,
            location=self._locate_excerpt(full_text, sentence),
            confidence=0.55,
            metadata={"source": "heuristic"},
        )

    def _split_sentences(self, text: str) -> List[str]:
        return [item.strip() for item in re.split(r"(?<=[。！？!?])\s+|\n{2,}", text) if item.strip()]

    def _locate_excerpt(self, full_text: str, excerpt: str) -> Dict[str, Any]:
        index = full_text.find(excerpt)
        if index >= 0:
            return {
                "char_start": index,
                "char_end": index + len(excerpt),
                "paragraph_index": full_text[:index].count("\n\n"),
            }

        normalized_excerpt = self._normalize_text(excerpt)
        if not normalized_excerpt:
            return {}
        paragraphs = [item for item in full_text.split("\n\n") if item.strip()]
        for paragraph_index, paragraph in enumerate(paragraphs):
            if normalized_excerpt in self._normalize_text(paragraph):
                char_start = full_text.find(paragraph)
                return {
                    "char_start": char_start,
                    "char_end": char_start + len(paragraph),
                    "paragraph_index": paragraph_index,
                }
        return {}

    def _parse_severity(self, value: Any) -> ReviewSeverity:
        normalized = str(value or "medium").strip().lower()
        mapping = {
            "low": ReviewSeverity.LOW,
            "medium": ReviewSeverity.MEDIUM,
            "high": ReviewSeverity.HIGH,
        }
        return mapping.get(normalized, ReviewSeverity.MEDIUM)

    def _is_english_dominant(self, sentence: str) -> bool:
        english_chars = sum(1 for char in sentence if ("A" <= char <= "Z") or ("a" <= char <= "z"))
        chinese_chars = sum(1 for char in sentence if "\u4e00" <= char <= "\u9fff")
        return english_chars > chinese_chars * 2 and english_chars >= 12

    def _is_heading_like(self, sentence: str) -> bool:
        stripped = sentence.strip()
        if stripped.startswith("#"):
            return True
        if re.match(r"^(?:[IVX]+\.?\s+|[A-Z]\.\s+)", stripped):
            return True
        if len(stripped) <= 18 and stripped.endswith((":", "：")):
            return True
        return False

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", "", text).lower()
