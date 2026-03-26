"""Built-in review templates."""

from __future__ import annotations

from importlib.resources import files


def get_default_review_template_path() -> str:
    """Return the built-in default structure template path."""
    return str(files("tencent_doc_review.templates").joinpath("default_product_research_structure_template.md"))


def read_default_review_template() -> str:
    """Return the built-in default structure template content."""
    return files("tencent_doc_review.templates").joinpath(
        "default_product_research_structure_template.md"
    ).read_text(encoding="utf-8")


def get_default_review_rules_path() -> str:
    """Return the built-in default review rules path."""
    return str(files("tencent_doc_review.templates").joinpath("default_product_research_review_rules.md"))


def read_default_review_rules() -> str:
    """Return the built-in default review rules content."""
    return files("tencent_doc_review.templates").joinpath(
        "default_product_research_review_rules.md"
    ).read_text(encoding="utf-8")


__all__ = [
    "get_default_review_template_path",
    "get_default_review_rules_path",
    "read_default_review_rules",
    "read_default_review_template",
]
