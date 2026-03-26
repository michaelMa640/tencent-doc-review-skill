"""Write review annotations back into a `.docx` file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from docx import Document
from docx.shared import RGBColor


@dataclass
class WordAnnotation:
    """Annotation to be applied to a paragraph in a Word document."""

    paragraph_index: int
    title: str
    comment: str
    severity: str = "medium"
    source_excerpt: str = ""
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class AnnotatedWordDocument:
    """Result of exporting an annotated Word document."""

    source_path: Path
    output_path: Path
    annotation_count: int
    metadata: Dict[str, object] = field(default_factory=dict)


class WordAnnotator:
    """Apply visible inline markers and an annotation appendix to `.docx` files.

    `python-docx` currently does not expose a stable high-level Word comment API.
    For the MVP we use an explicit in-document annotation block so the exported
    `.docx` remains reviewable on both Windows and macOS.
    """

    def annotate(
        self,
        source_path: Path,
        output_path: Path,
        annotations: List[WordAnnotation],
        document_title: Optional[str] = None,
    ) -> AnnotatedWordDocument:
        source = Path(source_path)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        document = Document(source)
        annotations_by_paragraph = {item.paragraph_index: [] for item in annotations}
        for item in annotations:
            annotations_by_paragraph[item.paragraph_index].append(item)

        for index, paragraph in enumerate(document.paragraphs):
            paragraph_annotations = annotations_by_paragraph.get(index, [])
            if not paragraph_annotations:
                continue
            run = paragraph.add_run(f" [审核标记:{len(paragraph_annotations)}]")
            run.font.color.rgb = self._severity_color(paragraph_annotations[0].severity)

        document.add_page_break()
        document.add_heading("AI 审核批注", level=1)
        if document_title:
            document.add_paragraph(f"文档标题: {document_title}")

        if not annotations:
            document.add_paragraph("未生成批注。")
        else:
            for idx, annotation in enumerate(annotations, start=1):
                document.add_heading(f"{idx}. {annotation.title}", level=2)
                document.add_paragraph(f"段落索引: {annotation.paragraph_index}")
                document.add_paragraph(f"严重级别: {annotation.severity}")
                if annotation.source_excerpt:
                    document.add_paragraph(f"命中原文: {annotation.source_excerpt}")
                document.add_paragraph(annotation.comment)

        document.save(output)
        return AnnotatedWordDocument(
            source_path=source,
            output_path=output,
            annotation_count=len(annotations),
            metadata={"document_title": document_title or source.stem},
        )

    def _severity_color(self, severity: str) -> RGBColor:
        normalized = severity.lower()
        if normalized == "high":
            return RGBColor(0xC0, 0x00, 0x00)
        if normalized == "low":
            return RGBColor(0x00, 0x66, 0x33)
        return RGBColor(0xB4, 0x5F, 0x06)
