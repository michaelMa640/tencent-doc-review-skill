"""Detect internal contradictions or inconsistent statements."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from loguru import logger

from ..domain.review_models import ReviewIssue, ReviewIssueType, ReviewSeverity
from ..llm.base import LLMClient
from ..llm.structured_output import extract_json_payload


class ConsistencyReviewer:
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
        try:
            response = await self._analyze_with_retry(self._build_prompt(text, context or {}))
            payload = self._extract_json_payload(response.content)
            return self._parse_payload(payload, text)
        except Exception as exc:  # pragma: no cover - provider/network path
            logger.warning("ConsistencyReviewer LLM review failed: {}", exc)
            return []

    async def _analyze_with_retry(self, prompt: str) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self.llm.analyze(prompt, analysis_type="general", temperature=self.temperature),
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
            "You are checking a Chinese product research report for internal contradictions.\n"
            "Focus only on real conflicts, such as inconsistent pricing, feature support, release timing, metrics, or version descriptions.\n"
            "Return exactly one JSON object and nothing else. Do not use markdown code fences.\n"
            'Schema: {"issues":[{"excerpt_a":"...","excerpt_b":"...","description":"中文说明","suggestion":"中文建议","severity":"low|medium|high"}]}\n'
            'If no contradiction exists, return {"issues":[]}.\n'
            f"Context: {json.dumps(context, ensure_ascii=False)}\n\nText:\n{text}"
        )

    def _extract_json_payload(self, content: str) -> Any:
        return extract_json_payload(content)

    def _parse_payload(self, payload: Any, full_text: str) -> List[ReviewIssue]:
        if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
            return []
        issues: List[ReviewIssue] = []
        for item in payload["issues"]:
            if not isinstance(item, dict):
                continue
            excerpt_a = str(item.get("excerpt_a") or "").strip()
            excerpt_b = str(item.get("excerpt_b") or "").strip()
            description = str(item.get("description") or "").strip()
            if not description or not excerpt_a:
                continue
            location = self._locate_excerpt(full_text, excerpt_a)
            issues.append(
                ReviewIssue(
                    issue_type=ReviewIssueType.CONSISTENCY,
                    severity=self._parse_severity(item.get("severity")),
                    title="前后矛盾",
                    description=description,
                    suggestion=str(item.get("suggestion") or "请复核前后表述并统一口径。").strip(),
                    source_excerpt=excerpt_a if not excerpt_b else f"{excerpt_a} / {excerpt_b}",
                    location=location,
                    confidence=0.7,
                    metadata={"excerpt_a": excerpt_a, "excerpt_b": excerpt_b, "anchor_preference": "document_end"},
                )
            )
        return issues

    def _locate_excerpt(self, full_text: str, excerpt: str) -> Dict[str, Any]:
        index = full_text.find(excerpt)
        if index < 0:
            return {}
        return {
            "char_start": index,
            "char_end": index + len(excerpt),
            "paragraph_index": full_text[:index].count("\n\n"),
        }

    def _parse_severity(self, value: Any) -> ReviewSeverity:
        mapping = {"low": ReviewSeverity.LOW, "medium": ReviewSeverity.MEDIUM, "high": ReviewSeverity.HIGH}
        return mapping.get(str(value or "medium").strip().lower(), ReviewSeverity.MEDIUM)
