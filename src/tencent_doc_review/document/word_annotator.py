"""Write review annotations back into a `.docx` file as native Word comments."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from docx import Document
from docx.document import Document as DocumentObject
from docx.text.run import Run


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
    """Apply review annotations as native Word comments."""

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
        if output.exists():
            output.unlink()

        document = Document(source)

        for annotation in annotations:
            paragraph = self._resolve_paragraph(document, annotation.paragraph_index)
            anchor_run = self._resolve_anchor_run(paragraph)
            document.add_comment(
                runs=anchor_run,
                text=self._build_comment_text(annotation),
                author="AI Review",
                initials="AI",
            )

        document.save(output)
        return AnnotatedWordDocument(
            source_path=source,
            output_path=output,
            annotation_count=len(annotations),
            metadata={
                "document_title": document_title or source.stem,
                "comment_mode": "native",
            },
        )

    def _resolve_paragraph(self, document: DocumentObject, paragraph_index: int):
        paragraphs = document.paragraphs
        if not paragraphs:
            return document.add_paragraph("")
        if 0 <= paragraph_index < len(paragraphs):
            return paragraphs[paragraph_index]
        return paragraphs[0]

    def _resolve_anchor_run(self, paragraph) -> Run:
        if paragraph.runs:
            return paragraph.runs[0]
        return paragraph.add_run(" ")

    def _build_comment_text(self, annotation: WordAnnotation) -> str:
        parts = [f"[{annotation.severity.upper()}] {annotation.title}", annotation.comment]
        if annotation.source_excerpt:
            parts.append(f"命中原文：{annotation.source_excerpt}")
        return "\n".join(part for part in parts if part)
