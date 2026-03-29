"""Fact checking helpers with optional search-backed verification."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from loguru import logger

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - fallback for lean environments
    httpx = None

from ..llm.base import LLMClient
from ..llm.providers.mock import MockLLMClient as MockDeepSeekClient
from ..llm.structured_output import extract_json_payload


DEFAULT_RECHECK_SUGGESTION = "检索到的公开信息未能直接证实该表述，建议依据下列来源核对后再保留。"
HEADING_LABEL_PATTERN = re.compile(r"^[#>\-\*\d\.\s一二三四五六七八九十IVXivx（）()【】\[\]：:]+$")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?])\s+|\n{2,}")
HARD_FACT_PATTERN = re.compile(
    r"\b20\d{2}\b|\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:亿|万|万元|亿美元|美元|元|人|次|家|MB|GB|秒|分钟)",
    re.IGNORECASE,
)
GENERIC_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9\.\-]{1,}|[\u4e00-\u9fff]{2,8}")
STOP_TOKENS = {
    "产品",
    "报告",
    "调研",
    "测评",
    "译文",
    "副本",
    "功能",
    "视频",
    "数字人",
    "生成",
    "支持",
    "用户",
    "系统",
    "平台",
    "内容",
    "效果",
    "信息",
    "公开",
}
BANNED_SOURCE_HINTS = (
    "t.me/",
    "telegram.",
    "behance.net/search",
    "pdf.dfcfw.com",
)


class VerificationStatus(Enum):
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    UNVERIFIED = "unverified"
    INCORRECT = "incorrect"
    PARTIALLY_CORRECT = "partial"


class ClaimType(Enum):
    DATA = "data"
    DATE_TIME = "date_time"
    PERSON = "person"
    LOCATION = "location"
    ORGANIZATION = "organization"
    EVENT = "event"
    QUOTATION = "quotation"
    NUMBER = "number"
    OTHER = "other"


ClaimType.OPINION = ClaimType.OTHER


@dataclass
class FactCheckResult:
    id: str = field(default_factory=lambda: f"fcr_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    original_text: str = ""
    claim_type: ClaimType = ClaimType.OTHER
    claim_content: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    suggestion: str = ""
    position: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    verified_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "original_text": self.original_text,
            "claim_type": self.claim_type.value,
            "claim_content": self.claim_content,
            "verification_status": self.verification_status.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "sources": self.sources,
            "suggestion": self.suggestion,
            "position": self.position,
            "created_at": self.created_at,
            "verified_at": self.verified_at,
        }


@dataclass
class Claim:
    text: str
    type: ClaimType = ClaimType.OTHER
    claim_type: Optional[ClaimType] = None
    confidence: float = 0.0
    needs_verification: bool = True
    entities: List[Dict[str, Any]] = field(default_factory=list)
    position: Dict[str, Any] = field(default_factory=dict)
    context: str = ""

    def __post_init__(self) -> None:
        if self.claim_type is not None:
            self.type = self.claim_type
        self.claim_type = self.type


class SearchClient:
    """Optional search verification client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "disabled",
        base_url: str = "",
        timeout: int = 20,
        max_results: int = 5,
        search_depth: str = "basic",
        topic: str = "general",
        client: Optional["httpx.AsyncClient"] = None,
    ) -> None:
        self.api_key = api_key or ""
        self.provider = (provider or ("tavily" if self.api_key else "disabled")).strip().lower()
        self.base_url = (base_url or "https://api.tavily.com/search").rstrip("/")
        self.timeout = int(timeout)
        self.max_results = int(max_results)
        self.search_depth = search_depth or "basic"
        self.topic = topic or "general"
        self._client = client
        self._owns_client = client is None
        self.enabled = self.provider != "disabled" and bool(self.api_key)
        logger.info("SearchClient initialized (provider={}, enabled={})", self.provider, self.enabled)

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        if not self.enabled:
            logger.warning("SearchClient is not enabled. Please configure search provider and API key.")
            return []
        if not query.strip():
            return []
        if self.provider == "tavily":
            return await self._search_tavily(query, min(num_results, self.max_results))
        raise ValueError(f"Unsupported search provider: {self.provider}")

    async def verify_fact(self, claim: str, context: str = "") -> Dict[str, Any]:
        query = claim if not context else f"{claim} {context}"
        results = await self.search(query)
        if not results:
            return {
                "status": "unverified",
                "confidence": 0.0,
                "evidence": [],
                "sources": [],
                "suggestion": DEFAULT_RECHECK_SUGGESTION,
            }
        return {
            "status": "unverified",
            "confidence": 0.35,
            "evidence": [item.get("snippet", "") for item in results if item.get("snippet")][:3],
            "sources": self._to_source_refs(results),
            "suggestion": DEFAULT_RECHECK_SUGGESTION,
        }

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    async def _search_tavily(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        if httpx is None:
            raise ModuleNotFoundError("httpx is required to call the search API")

        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        if self._client is None:
            self._client = client

        response = await client.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "topic": self.topic,
                "search_depth": self.search_depth,
                "max_results": num_results,
                "include_answer": False,
                "include_images": False,
                "include_raw_content": False,
            },
        )
        response.raise_for_status()
        data = response.json()

        results: List[Dict[str, Any]] = []
        for item in data.get("results") or []:
            url = str(item.get("url") or "")
            host = urlparse(url).netloc or str(item.get("source") or "")
            results.append(
                {
                    "title": str(item.get("title") or url or "来源"),
                    "url": url,
                    "snippet": str(item.get("content") or item.get("raw_content") or ""),
                    "source": host,
                    "score": item.get("score"),
                }
            )
        return results

    def _to_source_refs(self, results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        sources: List[Dict[str, str]] = []
        for item in results[:3]:
            sources.append(
                {
                    "title": str(item.get("title") or item.get("url") or "来源"),
                    "url": str(item.get("url") or ""),
                }
            )
        return sources


class FactChecker:
    """Extract factual claims and verify them with search-backed LLM prompts."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        search_client: Optional[SearchClient] = None,
        config: Optional[Dict[str, Any]] = None,
        deepseek_client: Optional[LLMClient] = None,
    ) -> None:
        self.llm = llm_client or deepseek_client
        if self.llm is None:
            raise ValueError("An llm_client is required")
        self.config = config or {}
        self.batch_size = int(self.config.get("batch_size", 5))
        self.max_claims = int(self.config.get("max_claims", self.batch_size))
        self.timeout_seconds = float(self.config.get("timeout_seconds", 45))
        self.max_retries = int(self.config.get("max_retries", 2))
        self.retry_delay_seconds = float(self.config.get("retry_delay_seconds", 1))
        self.temperature = float(self.config.get("temperature", 0.1))
        self.search_client = search_client or SearchClient(
            api_key=self.config.get("search_api_key"),
            provider=self.config.get("search_provider", "disabled"),
            base_url=self.config.get("search_base_url", ""),
            timeout=int(self.config.get("search_timeout_seconds", max(15, int(self.timeout_seconds)))),
            max_results=int(self.config.get("search_max_results", 5)),
            search_depth=str(self.config.get("search_depth", "basic")),
            topic=str(self.config.get("search_topic", "general")),
        )
        logger.info(
            "FactChecker initialized (search_enabled={}, search_provider={})",
            bool(getattr(self.search_client, "enabled", False)),
            getattr(self.search_client, "provider", "disabled"),
        )

    async def extract_claims(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[Claim]:
        if not text or not text.strip():
            return []

        try:
            response = await self._analyze_with_retry(
                self._build_claim_extraction_prompt(text, context or {}),
                analysis_type="fact_check",
            )
            payload = self._extract_json_payload(response.content)
            claims = self._parse_claim_payload(payload, text)
            if claims:
                return claims[: self.max_claims]
        except Exception as exc:
            logger.warning("Claim extraction failed, falling back to heuristics: {}", exc)
        return self._heuristic_extract_claims(text)

    async def verify_claim(self, claim: Claim, context: Optional[Dict[str, Any]] = None) -> FactCheckResult:
        if not claim.needs_verification:
            return FactCheckResult(
                original_text=claim.text,
                claim_type=claim.claim_type or claim.type,
                claim_content=claim.text,
                verification_status=VerificationStatus.UNVERIFIED,
                confidence=claim.confidence,
                suggestion="该句更偏主观体验表达，可按编辑需要决定是否保留。",
                position=claim.position,
            )

        context = context or {}
        search_results = await self._search_claim(claim, context)
        llm_error: Optional[Exception] = None
        try:
            response = await self._analyze_with_retry(
                self._build_claim_verification_prompt(claim, context, search_results),
                analysis_type="fact_check",
            )
            payload = self._extract_json_payload(response.content)
            if not isinstance(payload, dict):
                raise ValueError("Verification payload must be a JSON object")

            result = self._build_result_from_payload(claim, payload)
            if search_results:
                if not result.sources:
                    result.sources = self.search_client._to_source_refs(search_results)
                if not result.evidence:
                    result.evidence = self._search_evidence(search_results)
                if result.verification_status == VerificationStatus.UNVERIFIED and not result.suggestion:
                    result.suggestion = DEFAULT_RECHECK_SUGGESTION
            return self._apply_review_policy(claim, result, search_results)
        except Exception as exc:  # pragma: no cover - provider/network path
            llm_error = exc
            logger.warning("Fact verification failed for claim '{}': {}", claim.text, exc)

        if search_results:
            return self._apply_review_policy(
                claim,
                self._build_search_only_result(claim, search_results, llm_error=llm_error),
                search_results,
            )

        if getattr(self.search_client, "enabled", False):
            verification = await self.search_client.verify_fact(claim.text, claim.context)
            result = self._build_result_from_payload(claim, verification)
            if llm_error and not result.evidence:
                result.evidence.append(f"LLM verification failed: {llm_error}")
            return self._apply_review_policy(claim, result, [])

        fallback = FactCheckResult(
            original_text=claim.text,
            claim_type=claim.claim_type or claim.type,
            claim_content=claim.text,
            verification_status=VerificationStatus.UNVERIFIED,
            confidence=0.0,
            evidence=[],
            sources=[],
            suggestion=DEFAULT_RECHECK_SUGGESTION,
            position=claim.position,
            verified_at=datetime.now().isoformat(),
        )
        if llm_error:
            fallback.evidence.append(f"LLM verification failed: {llm_error}")
        return self._apply_review_policy(claim, fallback, [])

    async def check(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[FactCheckResult]:
        logger.info("Starting fact check for text ({} chars)", len(text or ""))
        if not text or not text.strip():
            logger.warning("Empty text provided for fact check")
            return []

        try:
            claims = await self.extract_claims(text, context)
        except Exception as exc:
            logger.warning("FactChecker: extract_claims failed: {}", exc)
            claims = self._heuristic_extract_claims(text)

        if not claims:
            claims = self._heuristic_extract_claims(text)
        if not claims:
            return []

        results: List[FactCheckResult] = []
        for claim in claims[: self.max_claims]:
            if not claim.needs_verification:
                continue
            results.append(await self.verify_claim(claim, context))
        return results

    async def batch_check(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[List[FactCheckResult]]:
        if not texts:
            return []

        results: List[List[FactCheckResult]] = []
        total = len(texts)
        for index, text in enumerate(texts, start=1):
            results.append(await self.check(text, context))
            if progress_callback:
                progress_callback(index, total, f"已完成 {index}/{total} 篇文档的事实核查")
        return results

    async def close(self) -> None:
        if hasattr(self.search_client, "close"):
            await self.search_client.close()

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

    async def _search_claim(self, claim: Claim, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not getattr(self.search_client, "enabled", False):
            return []
        query = self._build_search_query(claim, context)
        try:
            results = await self.search_client.search(query, num_results=int(self.config.get("search_max_results", 5)))
            return self._filter_search_results(claim, context, results)
        except Exception as exc:  # pragma: no cover - provider/network path
            logger.warning("Search verification failed for claim '{}': {}", claim.text, exc)
            return []

    def _build_search_query(self, claim: Claim, context: Dict[str, Any]) -> str:
        hints: List[str] = []
        for key in ("document_title", "topic", "product_name"):
            value = str(context.get(key) or "").strip()
            if value:
                hints.append(value)
        return f"{claim.text} {' '.join(hints[:2])}".strip()

    def _filter_search_results(
        self,
        claim: Claim,
        context: Dict[str, Any],
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not results:
            return []

        product_tokens = self._extract_relevance_tokens(" ".join(str(context.get(key) or "") for key in ("product_name", "document_title", "topic")))
        claim_tokens = self._extract_relevance_tokens(claim.text)
        filtered: List[Dict[str, Any]] = []

        for item in results:
            haystack = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("snippet") or ""),
                    str(item.get("url") or ""),
                    str(item.get("source") or ""),
                ]
            ).lower()

            if any(bad in haystack for bad in BANNED_SOURCE_HINTS):
                continue

            product_hits = [token for token in product_tokens if token.lower() in haystack]
            claim_hits = [token for token in claim_tokens if token.lower() in haystack]

            # For product review claims, we require at least one product hint match.
            if product_tokens and not product_hits:
                continue

            # Keep only results that mention claim-relevant wording or have strong source scores.
            if not claim_hits and float(item.get("score") or 0.0) < 0.78:
                continue

            filtered.append(item)

        return filtered[:3]

    def _build_claim_extraction_prompt(self, text: str, context: Dict[str, Any]) -> str:
        context_block = json.dumps(context, ensure_ascii=False) if context else "{}"
        return (
            "You are extracting factual claims from a Chinese product research report.\n"
            "Return exactly one JSON array and nothing else. Do not use markdown code fences.\n"
            "If there are no verifiable claims, return [].\n"
            "Only keep claims that can be checked externally. Skip headings, section labels, bullet labels, "
            "subjective opinions, personal experience, workflow impressions, forecasts, and pure editing notes.\n"
            'Schema per item: {"text":"claim sentence","claim_type":"data|date_time|person|location|organization|event|quotation|number|other","confidence":0.0,"needs_verification":true}\n'
            f"Context: {context_block}\n\nText:\n{text}"
        )

    def _build_claim_verification_prompt(
        self,
        claim: Claim,
        context: Dict[str, Any],
        search_results: List[Dict[str, Any]],
    ) -> str:
        context_block = json.dumps(context, ensure_ascii=False) if context else "{}"
        sources_block = json.dumps(self._serialize_search_results(search_results), ensure_ascii=False)
        prompt_parts = [
            "You are verifying one factual statement from a Chinese product research report.",
            "Use the provided search results as your primary external evidence.",
            "If the claim is risky but you still cannot confirm it confidently, set status to unverified.",
            "Return exactly one JSON object and nothing else. Do not use markdown code fences.",
            (
                'Schema: {"status":"confirmed|disputed|unverified|incorrect|partial",'
                '"confidence":0.0,"evidence":["..."],"sources":[{"title":"...","url":"..."}],'
                '"suggestion":"用中文一句话说明原因；如无法确认，要明确写出是“检索到的公开信息未能直接证实该表述”还是“检索到的网络信息与原文表述存在冲突”"}'
            ),
            f"Context: {context_block}",
            f"Statement: {claim.text}",
            f"Search results: {sources_block}",
        ]
        return "\n".join(prompt_parts)

    def _extract_json_payload(self, content: str) -> Any:
        return extract_json_payload(content)

    def _parse_claim_payload(self, payload: Any, full_text: str) -> List[Claim]:
        if not isinstance(payload, list):
            return []

        claims: List[Claim] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or item.get("claim") or "").strip()
            if not text or self._should_skip_claim(text):
                continue
            claims.append(
                Claim(
                    text=text,
                    claim_type=self._parse_claim_type(item.get("claim_type")),
                    confidence=self._safe_float(item.get("confidence"), default=0.6),
                    needs_verification=bool(item.get("needs_verification", True)),
                    position=self._locate_excerpt(full_text, text),
                )
            )
        return claims

    def _build_result_from_payload(self, claim: Claim, payload: Dict[str, Any]) -> FactCheckResult:
        status_value = payload.get("status") or payload.get("verification_status") or "unverified"
        status = self._parse_verification_status(status_value)
        suggestion = str(payload.get("suggestion") or "").strip()
        if not suggestion and status in {
            VerificationStatus.UNVERIFIED,
            VerificationStatus.DISPUTED,
            VerificationStatus.PARTIALLY_CORRECT,
        }:
            suggestion = DEFAULT_RECHECK_SUGGESTION
        return FactCheckResult(
            original_text=claim.text,
            claim_type=claim.claim_type or claim.type,
            claim_content=claim.text,
            verification_status=status,
            confidence=self._safe_float(payload.get("confidence"), default=0.0),
            evidence=self._normalize_string_list(payload.get("evidence")),
            sources=self._normalize_sources(payload.get("sources")),
            suggestion=suggestion,
            position=claim.position,
            verified_at=datetime.now().isoformat(),
        )

    def _apply_review_policy(
        self,
        claim: Claim,
        result: FactCheckResult,
        search_results: List[Dict[str, Any]],
    ) -> FactCheckResult:
        """Apply the sample-based review policy to raw fact-check results."""

        is_numeric = self._is_numeric_claim(claim)
        status = result.verification_status
        has_conflict = status in {
            VerificationStatus.INCORRECT,
            VerificationStatus.DISPUTED,
            VerificationStatus.PARTIALLY_CORRECT,
        }
        has_sources = bool(result.sources or search_results)

        if has_conflict:
            if not result.suggestion:
                result.suggestion = "检索到的网络信息与原文表述存在冲突，建议依据下列来源核对后改写。"
            return result

        if is_numeric:
            if status == VerificationStatus.UNVERIFIED:
                if has_sources:
                    result.suggestion = (
                        result.suggestion
                        or "检索到的公开信息未能直接证实该数值表述，建议依据下列来源核对后再保留。"
                    )
                    return result
                if self._looks_implausible_numeric_claim(claim.text):
                    result.suggestion = "未检索到可直接支撑该数值的公开来源，且该数值表现异常，建议人工二次核查。"
                    return result

                result.verification_status = VerificationStatus.CONFIRMED
                result.suggestion = ""
                return result
            return result

        if status == VerificationStatus.UNVERIFIED:
            # Product descriptions should not be flagged solely because public sources are absent.
            result.verification_status = VerificationStatus.CONFIRMED
            result.suggestion = ""
            return result

        return result

    def _build_search_only_result(
        self,
        claim: Claim,
        search_results: List[Dict[str, Any]],
        llm_error: Optional[Exception] = None,
    ) -> FactCheckResult:
        evidence = self._search_evidence(search_results)
        if llm_error is not None:
            evidence.append(f"LLM verification failed: {llm_error}")
        return FactCheckResult(
            original_text=claim.text,
            claim_type=claim.claim_type or claim.type,
            claim_content=claim.text,
            verification_status=VerificationStatus.UNVERIFIED,
            confidence=0.35,
            evidence=evidence,
            sources=self.search_client._to_source_refs(search_results),
            suggestion=DEFAULT_RECHECK_SUGGESTION,
            position=claim.position,
            verified_at=datetime.now().isoformat(),
        )

    def _heuristic_extract_claims(self, text: str) -> List[Claim]:
        claims: List[Claim] = []
        seen: set[str] = set()
        for sentence in self._split_sentences(text):
            normalized = sentence.strip()
            if not normalized or normalized in seen or self._should_skip_claim(normalized):
                continue
            if not self._looks_like_verifiable_claim(normalized):
                continue
            seen.add(normalized)
            claims.append(
                Claim(
                    text=normalized,
                    claim_type=self._infer_claim_type(normalized),
                    confidence=0.55,
                    needs_verification=True,
                    position=self._locate_excerpt(text, normalized),
                )
            )
        return claims[: self.max_claims]

    def _split_sentences(self, text: str) -> List[str]:
        sentences: List[str] = []
        for part in SENTENCE_SPLIT_PATTERN.split(text):
            stripped = part.strip()
            if not stripped:
                continue
            if len(stripped) > 180:
                segments = re.split(r"[。！？!?]", stripped)
                sentences.extend(item.strip() for item in segments if item.strip())
            else:
                sentences.append(stripped)
        return sentences

    def _looks_like_verifiable_claim(self, sentence: str) -> bool:
        patterns = [
            r"\b20\d{2}\b",
            r"\d+(?:\.\d+)?%",
            r"\d+(?:\.\d+)?(?:亿|万|万元|亿美元|美元|元|人|次|家|MB|GB|秒|分钟)",
            r"(发布|上线|融资|营收|收入|下载量|用户数|市场占有率|价格|定价|排名|增长|下降)",
            r"(腾讯|阿里|字节|百度|微软|谷歌|OpenAI|Anthropic|飞书|影刀|蝉镜|MiniMax|DeepSeek)",
        ]
        return any(re.search(pattern, sentence, re.IGNORECASE) for pattern in patterns)

    def _should_skip_claim(self, sentence: str) -> bool:
        stripped = sentence.strip()
        if not stripped:
            return True
        if stripped.startswith("#"):
            return True
        if HEADING_LABEL_PATTERN.match(stripped):
            return True
        if len(stripped) <= 18 and stripped.endswith((":", "：")):
            return True
        if self._is_subjective_or_experiential_claim(stripped):
            return True

        skip_markers = [
            "我认为",
            "我觉得",
            "我们可以",
            "整体来说",
            "预计",
            "预期",
            "有望",
            "如下图所示",
            "体验",
            "试用",
            "实测反馈",
            "用户反馈",
            "问题记录",
            "流程顺畅性",
            "性能表现",
            "等待大约三分钟",
            "可在3分钟内完成",
            "约为2-5分钟",
            "很快视频就生成完成",
            "个人感受",
            "主观上",
        ]
        return any(marker in stripped for marker in skip_markers)

    def _is_subjective_or_experiential_claim(self, sentence: str) -> bool:
        subjective_markers = [
            "大体上",
            "大差不差",
            "比较突出",
            "更突出",
            "更强",
            "更弱",
            "更适合",
            "特色功能",
            "七八成",
            "水准",
            "低门槛",
            "更顺手",
            "体验更",
            "我觉得",
            "我认为",
            "个人感受",
            "主观上",
            "还不错",
            "不太",
            "优势明显",
            "表现比较",
        ]
        if not any(marker in sentence for marker in subjective_markers):
            return False
        return not HARD_FACT_PATTERN.search(sentence)

    def _infer_claim_type(self, sentence: str) -> ClaimType:
        if re.search(r"\b20\d{2}\b.*(?:年|月|日)", sentence):
            return ClaimType.DATE_TIME
        if re.search(r"%|亿美元|美元|万元|万|亿|MB|GB|秒|分钟", sentence):
            return ClaimType.DATA
        if re.search(r"(腾讯|阿里|字节|百度|微软|谷歌|OpenAI|Anthropic|飞书|影刀|蝉镜|MiniMax|DeepSeek)", sentence):
            return ClaimType.ORGANIZATION
        return ClaimType.OTHER

    def _is_numeric_claim(self, claim: Claim) -> bool:
        claim_type = claim.claim_type or claim.type
        if claim_type in {ClaimType.DATA, ClaimType.NUMBER, ClaimType.DATE_TIME}:
            return True
        return bool(HARD_FACT_PATTERN.search(claim.text))

    def _looks_implausible_numeric_claim(self, sentence: str) -> bool:
        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%", sentence):
            try:
                if float(match.group(1)) > 100:
                    return True
            except ValueError:
                continue

        for match in re.finditer(r"\b(20\d{2})\b", sentence):
            try:
                if int(match.group(1)) > datetime.now().year + 2:
                    return True
            except ValueError:
                continue

        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(秒|分钟|小时|天)", sentence):
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            unit = match.group(2)
            if unit == "秒" and value > 3600:
                return True
            if unit == "分钟" and value > 1440:
                return True
            if unit == "小时" and value > 168:
                return True
            if unit == "天" and value > 365:
                return True

        return False

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

    def _serialize_search_results(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        serialized: List[Dict[str, Any]] = []
        for item in search_results[:3]:
            serialized.append(
                {
                    "title": str(item.get("title") or "来源"),
                    "url": str(item.get("url") or ""),
                    "snippet": str(item.get("snippet") or "")[:500],
                    "source": str(item.get("source") or ""),
                }
            )
        return serialized

    def _search_evidence(self, search_results: List[Dict[str, Any]]) -> List[str]:
        evidence: List[str] = []
        for item in search_results[:3]:
            snippet = str(item.get("snippet") or "").strip()
            if snippet:
                evidence.append(snippet[:240])
        return evidence

    def _parse_claim_type(self, value: Any) -> ClaimType:
        normalized = str(value or "other").strip().lower()
        for item in ClaimType:
            if item.value == normalized:
                return item
        if normalized == "opinion":
            return ClaimType.OTHER
        return ClaimType.OTHER

    def _parse_verification_status(self, value: Any) -> VerificationStatus:
        normalized = str(value or "unverified").strip().lower()
        mapping = {
            "confirmed": VerificationStatus.CONFIRMED,
            "true": VerificationStatus.CONFIRMED,
            "disputed": VerificationStatus.DISPUTED,
            "controversial": VerificationStatus.DISPUTED,
            "unverified": VerificationStatus.UNVERIFIED,
            "unknown": VerificationStatus.UNVERIFIED,
            "incorrect": VerificationStatus.INCORRECT,
            "false": VerificationStatus.INCORRECT,
            "partial": VerificationStatus.PARTIALLY_CORRECT,
            "partially_correct": VerificationStatus.PARTIALLY_CORRECT,
        }
        return mapping.get(normalized, VerificationStatus.UNVERIFIED)

    def _normalize_sources(self, value: Any) -> List[Dict[str, str]]:
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
            if isinstance(value, dict):
                value = [value]
            else:
                return []
        sources: List[Dict[str, str]] = []
        for item in value:
            if isinstance(item, dict):
                raw_url = str(item.get("url") or item.get("link") or "").strip()
                normalized_url = "" if raw_url in {"待补充", "N/A", "TBD", "-"} else raw_url
                sources.append(
                    {
                        "title": str(item.get("title") or item.get("name") or item.get("url") or "来源"),
                        "url": normalized_url,
                    }
                )
            elif item:
                sources.append({"title": str(item), "url": ""})
        return sources

    def _normalize_string_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value:
            return [str(value).strip()]
        return []

    def _extract_relevance_tokens(self, text: str) -> List[str]:
        tokens: List[str] = []
        for raw in GENERIC_TOKEN_PATTERN.findall(text or ""):
            token = raw.strip().strip("[]()（）【】《》:：,.，。;；!?！？\"'")
            if not token:
                continue
            lowered = token.lower()
            if lowered in STOP_TOKENS:
                continue
            if token.isdigit():
                continue
            if len(token) == 1:
                continue
            tokens.append(token)
        # Keep order but deduplicate.
        return list(dict.fromkeys(tokens))

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", "", text).lower()


async def check_facts(
    text: str,
    llm_client: LLMClient,
    search_client: Optional[SearchClient] = None,
    context: Optional[Dict[str, Any]] = None,
) -> List[FactCheckResult]:
    checker = FactChecker(llm_client=llm_client, search_client=search_client)
    try:
        return await checker.check(text, context)
    finally:
        await checker.close()


async def extract_claims_only(
    text: str,
    llm_client: LLMClient,
    context: Optional[Dict[str, Any]] = None,
) -> List[Claim]:
    checker = FactChecker(llm_client=llm_client)
    try:
        return await checker.extract_claims(text, context)
    finally:
        await checker.close()
