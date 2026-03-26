"""Parse `.docx` files into a normalized paragraph-oriented structure."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from docx import Document


@dataclass
class ParagraphNode:
    """Normalized paragraph block extracted from a Word document."""

    index: int
    text: str
    style_name: str = ""
    is_heading: bool = False
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class ParsedWordDocument:
    """Structured representation of a parsed Word document."""

    source_path: Path
    paragraphs: List[ParagraphNode]
    title: str = ""


class WordParser:
    """Read `.docx` files and extract paragraph-level structure."""

    def parse(self, file_path: Path) -> ParsedWordDocument:
        path = Path(file_path)
        document = Document(path)
        paragraphs: List[ParagraphNode] = []

        for index, paragraph in enumerate(document.paragraphs):
            text = paragraph.text.strip()
            style_name = paragraph.style.name if paragraph.style is not None else ""
            is_heading = style_name.lower().startswith("heading")
            paragraphs.append(
                ParagraphNode(
                    index=index,
                    text=text,
                    style_name=style_name,
                    is_heading=is_heading,
                )
            )

        title = next((node.text for node in paragraphs if node.text), path.stem)
        return ParsedWordDocument(
            source_path=path,
            paragraphs=paragraphs,
            title=title,
        )
