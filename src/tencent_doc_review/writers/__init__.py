"""Writers for reports and writeback strategies."""

from .annotation_adapter import AnnotationAdapter, AnnotationPayload, NoopAnnotationAdapter
from .doc_append_writer import DocAppendWriter
from .report_generator import ReportGenerator

__all__ = [
    "AnnotationAdapter",
    "AnnotationPayload",
    "NoopAnnotationAdapter",
    "DocAppendWriter",
    "ReportGenerator",
]
