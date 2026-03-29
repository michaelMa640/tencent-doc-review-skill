"""Document structure matching utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..llm.base import LLMClient


SECTION_ALIAS_MAP = {
    "产品概述": {"productoverview", "overview", "introduction"},
    "目标用户与市场定位": {"targetusersandmarketpositioning", "targetuser", "marketpositioning"},
    "核心功能与特性": {"corefeaturesandcharacteristics", "corefeatures", "features", "keyfeatures"},
    "实际使用体验": {"actualusageexperience", "practicalexperience", "hands-onexperience", "experience"},
    "竞品对比分析": {"competitorcomparisonanalysis", "competitiveanalysis", "comparison", "competitorcomparison"},
    "优势与不足": {"strengthsandweaknesses", "advantagesanddisadvantages", "prosandcons"},
    "价格与性价比": {"priceandcosteffectiveness", "pricecomparison", "pricingandvalue", "pricing"},
    "结论与推荐建议": {"conclusionandrecommendations", "conclusion", "recommendations"},
}


class MatchStatus(Enum):
    MATCHED = "matched"
    MISSING = "missing"
    MISPLACED = "misplaced"
    EXTRA = "extra"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class SectionType(Enum):
    HEADING = "heading"
    CUSTOM = "custom"


@dataclass
class Section:
    title: str
    type: SectionType = SectionType.HEADING
    level: int = 1
    order: int = 0
    content_summary: str = ""
    required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List["Section"] = field(default_factory=list)


@dataclass
class SectionMatch:
    template_section: Section
    document_section: Optional[Section] = None
    status: MatchStatus = MatchStatus.UNKNOWN
    similarity: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class StructureMatchResult:
    overall_score: float = 0.0
    section_matches: List[SectionMatch] = field(default_factory=list)
    document_sections: List[Section] = field(default_factory=list)
    template_sections: List[Section] = field(default_factory=list)

    @property
    def extra_sections(self) -> List[Section]:
        matched_titles = {
            match.document_section.title
            for match in self.section_matches
            if match.document_section is not None
        }
        return [section for section in self.document_sections if section.title not in matched_titles]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "section_matches": [
                {
                    "template_section": match.template_section.title,
                    "document_section": match.document_section.title if match.document_section else None,
                    "status": match.status.value,
                    "similarity": match.similarity,
                    "issues": match.issues,
                    "suggestions": match.suggestions,
                }
                for match in self.section_matches
            ],
        }


class StructureMatcher:
    """Simple heading-based structure matcher."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        config: Optional[Dict[str, Any]] = None,
        deepseek_client: Optional[LLMClient] = None,
    ) -> None:
        self.llm = llm_client or deepseek_client
        if self.llm is None:
            raise ValueError("An llm_client is required")
        self.config = config or {}

    async def match(
        self,
        document_text: str,
        template_text: str,
        context: Optional[Dict[str, Any]] = None,
        matching_mode: Optional[str] = None,
    ) -> StructureMatchResult:
        template_root = await self.parse_template(template_text, context)
        document_root = await self.parse_document(document_text, context)

        template_sections = [
            section for section in self._flatten_sections(template_root) if not self._is_template_container_title(section.title)
        ]
        document_sections = self._flatten_sections(document_root)
        document_titles = {self._canonical_key(section.title): section for section in document_sections}

        matches: List[SectionMatch] = []
        matched_count = 0

        for expected in template_sections:
            actual = document_titles.get(self._canonical_key(expected.title))
            if actual is not None:
                matched_count += 1
                matches.append(
                    SectionMatch(
                        template_section=expected,
                        document_section=actual,
                        status=MatchStatus.MATCHED,
                        similarity=1.0,
                    )
                )
            else:
                matches.append(
                    SectionMatch(
                        template_section=expected,
                        status=MatchStatus.MISSING,
                        issues=[f"缺少章节：{expected.title}"],
                        suggestions=[f"请补充章节“{expected.title}”。"],
                    )
                )

        overall_score = matched_count / len(template_sections) if template_sections else 1.0
        return StructureMatchResult(
            overall_score=overall_score,
            section_matches=matches,
            document_sections=document_sections,
            template_sections=template_sections,
        )

    async def _parse_structure_llm(self, text: str, is_template: bool = False) -> Section:
        return self._parse_headings(text, is_template=is_template)

    def _fallback_parse(self, text: str, is_template: bool = False) -> Section:
        return self._parse_headings(text, is_template=is_template)

    async def parse_template(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Section:
        return self._parse_headings(text, is_template=True)

    async def parse_document(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Section:
        return self._parse_headings(text, is_template=False)

    def _parse_headings(self, text: str, is_template: bool) -> Section:
        root = Section(title="Root", type=SectionType.CUSTOM, level=0, required=True)
        stack: List[Section] = [root]
        lines = text.splitlines()

        for index, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue

            heading = self._match_heading(line)
            if heading is None:
                if stack[-1] is not root:
                    summary = stack[-1].content_summary
                    stack[-1].content_summary = (summary + " " + line).strip()[:200]
                continue

            level, title = heading
            section = Section(
                title=title,
                type=SectionType.HEADING,
                level=level,
                order=index,
                required=is_template,
                metadata={"line_number": index},
            )

            while len(stack) > level:
                stack.pop()
            stack[-1].children.append(section)
            stack.append(section)

        return root

    def _match_heading(self, line: str) -> Optional[tuple[int, str]]:
        markdown_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if markdown_match:
            return len(markdown_match.group(1)), markdown_match.group(2).strip()

        roman_match = re.match(r"^([IVXLCM]+)[\.\)]\s+(.+)$", line, re.IGNORECASE)
        if roman_match:
            return 2, roman_match.group(2).strip()

        numbered_match = re.match(r"^(\d+)[\.\)]\s*(.+)$", line)
        if numbered_match:
            return 2, numbered_match.group(2).strip()

        ordered_chinese_match = re.match(r"^([一二三四五六七八九十]+)[、.．)]\s*(.+)$", line)
        if ordered_chinese_match:
            return 2, ordered_chinese_match.group(2).strip()

        chinese_match = re.match(r"^第[一二三四五六七八九十\d]+[章节]\s*(.+)$", line)
        if chinese_match:
            return 2, chinese_match.group(1).strip() or line

        canonical_titles = {self._normalize(title) for title in SECTION_ALIAS_MAP}
        if self._canonical_key(line) in canonical_titles:
            return 2, line.strip()

        return None

    def _flatten_sections(self, root: Section) -> List[Section]:
        sections: List[Section] = []

        def walk(node: Section) -> None:
            for child in node.children:
                sections.append(child)
                walk(child)

        walk(root)
        return sections

    def _normalize(self, title: str) -> str:
        normalized = title.strip().lower()
        normalized = re.sub(r"^\d+[\.\)、]\s*", "", normalized)
        normalized = re.sub(r"^[一二三四五六七八九十]+[\.\)、]\s*", "", normalized)
        normalized = re.sub(r"^(第[一二三四五六七八九十\d]+[章节部分篇])\s*", "", normalized)
        normalized = re.sub(r"^[ivxlcm]+[\.\)]\s*", "", normalized)
        normalized = re.sub(r"[：:()（）\-_/]", "", normalized)
        normalized = re.sub(r"\s+", "", normalized)
        return normalized

    def _is_template_container_title(self, title: str) -> bool:
        normalized = self._normalize(title)
        return normalized.endswith("模板") or normalized in {"模板", "审核模板", "调研模板"}

    def _canonical_key(self, title: str) -> str:
        normalized = self._normalize(title)
        for canonical_title, aliases in SECTION_ALIAS_MAP.items():
            if normalized == self._normalize(canonical_title):
                return self._normalize(canonical_title)
            if normalized in aliases:
                return self._normalize(canonical_title)
        return normalized


async def match_structure(
    document_text: str,
    template_text: str,
    llm_client: LLMClient,
    context: Optional[Dict[str, Any]] = None,
) -> StructureMatchResult:
    matcher = StructureMatcher(llm_client=llm_client)
    return await matcher.match(document_text, template_text, context)


async def parse_document_structure(
    text: str,
    llm_client: LLMClient,
    context: Optional[Dict[str, Any]] = None,
) -> Section:
    matcher = StructureMatcher(llm_client=llm_client)
    return await matcher.parse_document(text, context)
