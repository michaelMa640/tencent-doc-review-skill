"""Built-in review templates."""

from __future__ import annotations

from importlib.resources import files


def get_default_review_template_path() -> str:
    """Return the built-in default product research review template path."""
    return str(files("tencent_doc_review.templates").joinpath("default_product_research_review_template.md"))


def read_default_review_template() -> str:
    """Return the built-in default product research review template content."""
    return files("tencent_doc_review.templates").joinpath(
        "default_product_research_review_template.md"
    ).read_text(encoding="utf-8")


__all__ = [
    "get_default_review_template_path",
    "read_default_review_template",
]
