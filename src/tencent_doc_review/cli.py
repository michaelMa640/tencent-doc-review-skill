"""Command-line entrypoints for local text analysis workflows."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import click

from .config import get_settings
from .analyzer.document_analyzer import DocumentAnalyzer
from .llm.factory import create_llm_client


def _read_text(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


@click.group()
def main() -> None:
    """Tencent document review CLI."""


@main.command("doctor")
def doctor() -> None:
    """Show local configuration status."""
    settings = get_settings()
    click.echo("Configuration")
    click.echo(f"  LLM_PROVIDER: {settings.llm_provider}")
    click.echo(f"  LLM_API_KEY: {'set' if (settings.llm_api_key or settings.deepseek_api_key) else 'missing'}")
    click.echo(f"  TENCENT_DOCS_TOKEN: {'set' if settings.tencent_docs_token else 'missing'}")
    click.echo(f"  TENCENT_DOCS_CLIENT_ID: {'set' if settings.tencent_docs_client_id else 'missing'}")
    click.echo(f"  TENCENT_DOCS_OPEN_ID: {'set' if settings.tencent_docs_open_id else 'missing'}")


@main.command("analyze")
@click.option("--input-file", "input_file", required=True, type=click.Path(exists=True))
@click.option("--template-file", "template_file", type=click.Path(exists=True))
@click.option("--output", "output_path", type=click.Path())
@click.option("--format", "output_format", type=click.Choice(["markdown", "json"]), default="markdown")
def analyze(input_file: str, template_file: Optional[str], output_path: Optional[str], output_format: str) -> None:
    """Analyze a local document file."""
    asyncio.run(_analyze(input_file, template_file, output_path, output_format))


async def _analyze(
    input_file: str,
    template_file: Optional[str],
    output_path: Optional[str],
    output_format: str,
) -> None:
    settings = get_settings()
    client = create_llm_client(
        provider=settings.llm_provider,
        api_key=settings.llm_api_key or settings.deepseek_api_key,
        base_url=settings.llm_base_url or settings.deepseek_base_url,
        model=settings.llm_model or settings.deepseek_model,
        timeout=settings.request_timeout,
    )

    analyzer = DocumentAnalyzer(deepseek_client=client)
    result = await analyzer.analyze(
        document_text=_read_text(input_file) or "",
        template_text=_read_text(template_file),
        document_title=Path(input_file).name,
    )

    if output_format == "json":
        rendered = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    else:
        rendered = result.to_markdown()

    if output_path:
        Path(output_path).write_text(rendered, encoding="utf-8")
        click.echo(f"Saved analysis to {output_path}")
    else:
        click.echo(rendered)

    await client.close()
