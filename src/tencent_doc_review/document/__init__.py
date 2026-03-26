"""Word document parsing and annotation helpers."""

from .docx_compressor import DocxCompressionResult, DocxCompressor
from .word_annotator import WordAnnotation, WordAnnotator, AnnotatedWordDocument
from .word_parser import ParsedWordDocument, ParagraphNode, WordParser

__all__ = [
    "DocxCompressionResult",
    "DocxCompressor",
    "WordAnnotation",
    "WordAnnotator",
    "AnnotatedWordDocument",
    "ParsedWordDocument",
    "ParagraphNode",
    "WordParser",
]
