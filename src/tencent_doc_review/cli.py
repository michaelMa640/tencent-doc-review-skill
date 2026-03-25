"""Command-line entrypoints for local text analysis workflows."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import click

from .config import get_settings
from .analyzer.document_analyzer import DocumentAnalyzer
from .llm.factory import create_llm_client
from .tencent_doc_client import TencentDocClient
from .writers import DocAppendWriter, ReportGenerator


def _read_text(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def _create_tencent_doc_client() -> TencentDocClient:
    settings = get_settings()
    return TencentDocClient(
        access_token=settings.tencent_docs_token,
        client_id=settings.tencent_docs_client_id,
        open_id=settings.tencent_docs_open_id,
        base_url=settings.tencent_docs_base_url,
        timeout=settings.request_timeout,
        max_retries=settings.tencent_docs_max_retries,
        retry_delay=settings.tencent_docs_retry_delay,
    )


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
@click.option("--input-file", "input_file", type=click.Path(exists=True))
@click.option("--doc-id", "doc_id", type=str)
@click.option("--template-file", "template_file", type=click.Path(exists=True))
@click.option("--template-doc-id", "template_doc_id", type=str)
@click.option("--output", "output_path", type=click.Path())
@click.option("--format", "output_format", type=click.Choice(["markdown", "json", "html"]), default="markdown")
@click.option("--writeback-mode", "writeback_mode", type=click.Choice(["none", "append"]), default="none")
@click.option("--provider", "provider", type=str)
@click.option("--api-key", "api_key", type=str)
@click.option("--base-url", "base_url", type=str)
@click.option("--model", "model", type=str)
def analyze(
    input_file: Optional[str],
    doc_id: Optional[str],
    template_file: Optional[str],
    template_doc_id: Optional[str],
    output_path: Optional[str],
    output_format: str,
    writeback_mode: str,
    provider: Optional[str],
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
) -> None:
    """Analyze a local file or Tencent Docs document."""
    asyncio.run(
        _analyze(
            input_file,
            doc_id,
            template_file,
            template_doc_id,
            output_path,
            output_format,
            writeback_mode,
            provider,
            api_key,
            base_url,
            model,
        )
    )


async def _analyze(
    input_file: Optional[str],
    doc_id: Optional[str],
    template_file: Optional[str],
    template_doc_id: Optional[str],
    output_path: Optional[str],
    output_format: str,
    writeback_mode: str,
    provider: Optional[str],
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
) -> None:
    if bool(input_file) == bool(doc_id):
        raise click.UsageError("Provide exactly one of --input-file or --doc-id.")
    if template_file and template_doc_id:
        raise click.UsageError("Provide at most one of --template-file or --template-doc-id.")
    if writeback_mode != "none" and not doc_id:
        raise click.UsageError("Writeback is only supported with --doc-id.")

    settings = get_settings()
    client = create_llm_client(
        provider=provider or settings.llm_provider,
        api_key=api_key or settings.llm_api_key or settings.deepseek_api_key,
        base_url=base_url or settings.llm_base_url or settings.deepseek_base_url,
        model=model or settings.llm_model or settings.deepseek_model,
        timeout=settings.request_timeout,
    )

    doc_client: Optional[TencentDocClient] = None
    writeback_result = None
    try:
        if doc_id:
            doc_client = _create_tencent_doc_client()
            analyzer = DocumentAnalyzer(llm_client=client, mcp_client=doc_client)
            result = await analyzer.analyze_from_tencent_doc(
                file_id=doc_id,
                template_file_id=template_doc_id,
            )
            if writeback_mode == "append":
                writeback_result = await DocAppendWriter().write(doc_client, doc_id, result)
        else:
            analyzer = DocumentAnalyzer(llm_client=client)
            result = await analyzer.analyze(
                document_text=_read_text(input_file) or "",
                template_text=_read_text(template_file),
                document_title=Path(input_file or "").name,
            )

        rendered = ReportGenerator().render(result, output_format)

        if output_path:
            Path(output_path).write_text(rendered, encoding="utf-8")
            click.echo(f"Saved analysis to {output_path}")
        else:
            click.echo(rendered)
        if writeback_result is not None:
            click.echo(f"Writeback mode: {writeback_result.get('mode', 'append')}")
    finally:
        if doc_client is not None:
            await doc_client.close()
        await client.close()
