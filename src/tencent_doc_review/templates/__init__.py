"""Review template resolution helpers."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from ..config import get_settings

DEFAULT_RULES_FILENAME = "default_product_research_review_rules.md"
DEFAULT_STRUCTURE_FILENAME = "default_product_research_structure_template.md"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT_TEMPLATES_DIR = PROJECT_ROOT / "templates"


def _package_template_path(filename: str) -> Path:
    return Path(str(files("tencent_doc_review.templates").joinpath(filename)))


def _resolve_template_path(configured_path: str, filename: str) -> Path:
    candidates: list[Path] = []
    if configured_path.strip():
        candidates.append(Path(configured_path).expanduser())
    candidates.append(ROOT_TEMPLATES_DIR / filename)
    candidates.append(_package_template_path(filename))

    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Template file not found: {filename}")


def get_default_review_template_path() -> str:
    """Return the active structure template path."""
    settings = get_settings()
    return str(_resolve_template_path(settings.review_structure_template_path, DEFAULT_STRUCTURE_FILENAME))


def read_default_review_template() -> str:
    """Return the active structure template content."""
    return Path(get_default_review_template_path()).read_text(encoding="utf-8")


def get_default_review_rules_path() -> str:
    """Return the active review rules path."""
    settings = get_settings()
    return str(_resolve_template_path(settings.review_rules_template_path, DEFAULT_RULES_FILENAME))


def read_default_review_rules() -> str:
    """Return the active review rules content."""
    return Path(get_default_review_rules_path()).read_text(encoding="utf-8")


__all__ = [
    "get_default_review_template_path",
    "get_default_review_rules_path",
    "read_default_review_rules",
    "read_default_review_template",
]
