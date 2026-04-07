"""Command-line entrypoints for local text analysis workflows."""

from __future__ import annotations

import asyncio
import json
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import click

from .config import describe_env_file_candidates, get_effective_debug_output_dir, get_settings, reload_settings
from .access import (
    CommandMCPClient,
    MCPBridgeError,
    MCPDownloadPayload,
    MCPUploadPayload,
    TencentDocReference,
    UploadTarget,
    build_bridge_config,
)
from .analyzer.document_analyzer import DocumentAnalyzer
from .llm.factory import create_llm_client, resolve_llm_settings
from .skill import SkillRequest, SkillRuntimeInfo
from .templates import (
    get_default_review_rules_path,
    get_default_review_template_path,
    read_default_review_template,
)
from .tencent_doc_client import TencentDocClient
from .workflows import SkillPipeline
from .writers import DocAppendWriter, ReportGenerator


def _read_text(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def _default_openclaw_bridge_script() -> Path:
    return Path(__file__).resolve().parent / "access" / "openclaw_bridge.py"


def _detect_python_executable() -> str:
    if sys.executable:
        return sys.executable
    return shutil.which("python") or shutil.which("python3") or ""


def _detect_openclaw_executable() -> str:
    for name in ("openclaw.cmd", "openclaw"):
        resolved = shutil.which(name)
        if resolved:
            return resolved

    appdata = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
    if appdata.exists():
        return str(appdata)

    return ""


def _build_default_openclaw_bridge_args_text(openclaw_executable: str) -> str:
    bridge_script = _default_openclaw_bridge_script()
    args = [
        str(bridge_script),
        "--openclaw-executable",
        openclaw_executable,
        "--agent-id",
        "main",
        "--no-local",
    ]
    return subprocess.list2cmdline(args) if platform.system().lower() == "windows" else shlex.join(args)


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
    click.echo("  Mode notes:")
    click.echo("    - OpenClaw / Claude Code MCP mode: mainly uses bridge configuration and Tencent Docs MCP token/login state")
    click.echo("    - Tencent Docs OpenAPI direct mode: requires TENCENT_DOCS_TOKEN / CLIENT_ID / OPEN_ID")
    click.echo(f"  LLM_PROVIDER: {settings.llm_provider}")
    click.echo(f"  LLM_API_KEY: {'set' if (settings.llm_api_key or settings.deepseek_api_key) else 'missing'}")
    click.echo(f"  DEEPSEEK_API_KEY: {'set' if settings.deepseek_api_key else 'missing'}")
    click.echo(f"  MINIMAX_API_KEY: {'set' if settings.minimax_api_key else 'missing'}")
    click.echo(f"  TENCENT_DOCS_TOKEN: {'set' if settings.tencent_docs_token else 'missing'}")
    click.echo("  Tencent Docs OpenAPI direct mode only:")
    click.echo(f"    TENCENT_DOCS_CLIENT_ID: {'set' if settings.tencent_docs_client_id else 'missing'}")
    click.echo(f"    TENCENT_DOCS_OPEN_ID: {'set' if settings.tencent_docs_open_id else 'missing'}")
    click.echo(f"  SEARCH_PROVIDER: {settings.search_provider}")
    click.echo(f"  SEARCH_API_KEY: {'set' if settings.search_api_key else 'missing'}")
    click.echo(f"  FACT_CHECK_MODE: {settings.fact_check_mode}")
    click.echo(f"  SKILL_MCP_CLIENT: {settings.skill_mcp_client}")
    auto_openclaw = _detect_openclaw_executable()
    auto_python = _detect_python_executable()
    click.echo(f"  OPENCLAW_MCP_BRIDGE_EXECUTABLE: {'set' if settings.openclaw_mcp_bridge_executable else 'auto' if auto_python else 'missing'}")
    click.echo(f"  OPENCLAW executable discoverable: {'yes' if auto_openclaw else 'no'}")
    click.echo(f"  CLAUDE_CODE_MCP_BRIDGE_EXECUTABLE: {'set' if settings.claude_code_mcp_bridge_executable else 'missing'}")
    click.echo(f"  REVIEW_DEBUG_OUTPUT_DIR: {get_effective_debug_output_dir(settings.review_debug_output_dir)}")
    click.echo(f"  REVIEW_RULES_TEMPLATE_PATH: {get_default_review_rules_path()}")
    click.echo(f"  REVIEW_STRUCTURE_TEMPLATE_PATH: {get_default_review_template_path()}")
    click.echo("  ENV candidates:")
    for candidate in describe_env_file_candidates():
        click.echo(f"    - {candidate['path']} ({'exists' if candidate['exists'] else 'missing'})")


@main.command("debug-config")
def debug_config() -> None:
    """Print config discovery details for troubleshooting in different runtimes."""
    settings = reload_settings()
    payload = {
        "cwd": str(Path.cwd()),
        "python_executable": sys.executable,
        "env_candidates": describe_env_file_candidates(),
        "config_status": {
            "llm_provider": settings.llm_provider,
            "llm_api_key": bool(settings.llm_api_key or settings.deepseek_api_key or settings.minimax_api_key),
            "deepseek_api_key": bool(settings.deepseek_api_key),
            "minimax_api_key": bool(settings.minimax_api_key),
            "tencent_docs_token": bool(settings.tencent_docs_token),
            "search_provider": settings.search_provider,
            "search_api_key": bool(settings.search_api_key),
            "fact_check_mode": settings.fact_check_mode,
            "skill_mcp_client": settings.skill_mcp_client,
            "review_debug_output_dir": get_effective_debug_output_dir(settings.review_debug_output_dir),
            "review_rules_template_path": get_default_review_rules_path(),
            "review_structure_template_path": get_default_review_template_path(),
        },
    }
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@main.command("debug-doc")
@click.option("--doc-id", "doc_id", required=True, type=str)
def debug_doc(doc_id: str) -> None:
    """Print a safe summary of the Tencent Docs API response structure."""
    asyncio.run(_debug_doc(doc_id))


@main.command("debug-converter")
@click.option("--encoded-id", "encoded_id", required=True, type=str)
def debug_converter(encoded_id: str) -> None:
    """Print a safe summary of the Tencent Docs converter response."""
    asyncio.run(_debug_converter(encoded_id))


@main.command("list-files")
@click.option("--folder-id", "folder_id", type=str)
@click.option("--encoded-id", "encoded_id", type=str)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def list_files(folder_id: Optional[str], encoded_id: Optional[str], output_format: str) -> None:
    """List Tencent Docs files or resolve an encoded URL id into a real fileId."""
    asyncio.run(_list_files(folder_id, encoded_id, output_format))


@main.command("skill-info")
def skill_info() -> None:
    """Print shared skill runtime information for OpenClaw / Claude Code integration."""
    settings = get_settings()
    runtime = SkillRuntimeInfo(
        platform=platform.system().lower(),
        temp_root=str(Path(tempfile.gettempdir()) / "tencent-doc-review"),
    )
    payload = dict(runtime.__dict__)
    payload["default_mcp_client"] = settings.skill_mcp_client
    payload["default_fact_check_mode"] = settings.fact_check_mode
    payload["available_mcp_clients"] = {
        "mock": True,
        "openclaw": bool(settings.openclaw_mcp_bridge_executable or (_detect_python_executable() and _detect_openclaw_executable())),
        "claude_code": bool(settings.claude_code_mcp_bridge_executable),
    }
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@main.command("analyze")
@click.option("--input-file", "input_file", type=click.Path(exists=True))
@click.option("--doc-id", "doc_id", type=str)
@click.option("--template-file", "template_file", type=click.Path(exists=True))
@click.option("--template-doc-id", "template_doc_id", type=str)
@click.option("--default-template", "default_template", is_flag=True, help="Use the built-in default review template.")
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
    default_template: bool,
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
            default_template,
            output_path,
            output_format,
            writeback_mode,
            provider,
            api_key,
            base_url,
            model,
        )
    )


@main.command("skill-run")
@click.option("--doc-id", "doc_id", required=True, type=str)
@click.option("--title", "title", required=True, type=str)
@click.option("--target-folder-id", "target_folder_id", required=True, type=str)
@click.option("--target-space-id", "target_space_id", default="", type=str)
@click.option(
    "--target-space-type",
    "target_space_type",
    default="personal_space",
    type=click.Choice(["personal_space", "cloud_drive", "workspace"]),
)
@click.option("--target-path", "target_path", default="", type=str)
@click.option("--download-dir", "download_dir", default="", type=click.Path())
@click.option(
    "--mcp-client",
    "mcp_client_name",
    type=click.Choice(["mock", "openclaw", "claude_code"]),
)
@click.option("--bridge-executable", "bridge_executable", default="", type=str)
@click.option("--bridge-args", "bridge_args", default="", type=str)
@click.option("--provider", "provider", default="", type=str, help="LLM provider used during review.")
@click.option("--debug-dir", "debug_dir", default="", type=click.Path(), help="Write a local debug bundle for this run.")
def skill_run(
    doc_id: str,
    title: str,
    target_folder_id: str,
    target_space_id: str,
    target_space_type: str,
    target_path: str,
    download_dir: str,
    mcp_client_name: Optional[str],
    bridge_executable: str,
    bridge_args: str,
    provider: str,
    debug_dir: str,
    ) -> None:
    """Run the shared skill workflow with a local MCP client implementation."""
    asyncio.run(
        _skill_run(
            doc_id=doc_id,
            title=title,
            target_folder_id=target_folder_id,
            target_space_id=target_space_id,
            target_space_type=target_space_type,
            target_path=target_path,
            download_dir=download_dir,
            mcp_client_name=mcp_client_name,
            bridge_executable=bridge_executable,
            bridge_args=bridge_args,
            provider=provider,
            debug_dir=debug_dir,
        )
    )


@main.command("review-docx")
@click.option("--input-docx", "input_docx", required=True, type=click.Path(exists=True))
@click.option("--title", "title", default="", type=str)
@click.option("--output-dir", "output_dir", default="", type=click.Path())
@click.option("--provider", "provider", default="", type=str)
@click.option("--debug-dir", "debug_dir", default="", type=click.Path(), help="Write a local debug bundle for this run.")
def review_docx(
    input_docx: str,
    title: str,
    output_dir: str,
    provider: str,
    debug_dir: str,
) -> None:
    """Review a local DOCX and generate an annotated DOCX plus markdown report."""
    asyncio.run(
        _review_docx(
            input_docx=input_docx,
            title=title,
            output_dir=output_dir,
            provider=provider,
            debug_dir=debug_dir,
        )
    )


async def _analyze(
    input_file: Optional[str],
    doc_id: Optional[str],
    template_file: Optional[str],
    template_doc_id: Optional[str],
    default_template: bool,
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
    if default_template and (template_file or template_doc_id):
        raise click.UsageError("Do not combine --default-template with --template-file or --template-doc-id.")
    if writeback_mode != "none" and not doc_id:
        raise click.UsageError("Writeback is only supported with --doc-id.")

    resolved_template_text = read_default_review_template() if default_template else None

    settings = get_settings()
    llm_settings = resolve_llm_settings(
        settings=settings,
        provider=provider or settings.llm_provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=settings.request_timeout,
    )
    client = create_llm_client(**llm_settings)

    doc_client: Optional[TencentDocClient] = None
    writeback_result = None
    try:
        if doc_id:
            doc_client = _create_tencent_doc_client()
            analyzer = DocumentAnalyzer(llm_client=client, mcp_client=doc_client)
            result = await analyzer.analyze_from_tencent_doc(
                file_id=doc_id,
                template_file_id=template_doc_id,
                template_text=resolved_template_text,
            )
            if writeback_mode == "append":
                writeback_result = await DocAppendWriter().write(doc_client, doc_id, result)
        else:
            analyzer = DocumentAnalyzer(llm_client=client)
            result = await analyzer.analyze(
                document_text=_read_text(input_file) or "",
                template_text=_read_text(template_file) if template_file else resolved_template_text,
                document_title=Path(input_file or "").name,
            )

        rendered = ReportGenerator().render(result, output_format)

        if output_path:
            Path(output_path).write_text(rendered, encoding="utf-8")
            click.echo(f"Saved analysis to {output_path}")
        else:
            click.echo(rendered)
        if default_template:
            click.echo(f"Template: built-in default ({get_default_review_template_path()})")
        if writeback_result is not None:
            click.echo(f"Writeback mode: {writeback_result.get('mode', 'append')}")
    finally:
        if doc_client is not None:
            await doc_client.close()
        await client.close()


async def _review_docx(
    input_docx: str,
    title: str,
    output_dir: str,
    provider: str,
    debug_dir: str,
) -> None:
    settings = reload_settings()
    artifacts = await SkillPipeline().review_local_docx(
        input_path=input_docx,
        title=title,
        provider=provider or settings.llm_provider,
        output_dir=output_dir,
        debug_output_dir=get_effective_debug_output_dir(debug_dir or settings.review_debug_output_dir),
    )
    click.echo(json.dumps(asdict(artifacts), ensure_ascii=False, indent=2, default=str))


async def _debug_doc(doc_id: str) -> None:
    doc_client = _create_tencent_doc_client()
    try:
        payload = await doc_client.debug_document_response(doc_id)
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        await doc_client.close()


async def _debug_converter(encoded_id: str) -> None:
    doc_client = _create_tencent_doc_client()
    try:
        payload = await doc_client.debug_converter_response(encoded_id)
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        await doc_client.close()


async def _list_files(folder_id: Optional[str], encoded_id: Optional[str], output_format: str) -> None:
    if bool(folder_id) == bool(encoded_id):
        raise click.UsageError("Provide exactly one of --folder-id or --encoded-id.")

    doc_client = _create_tencent_doc_client()
    try:
        if encoded_id:
            file_id = await doc_client.convert_encoded_id_to_file_id(encoded_id)
            payload = {
                "encoded_id": encoded_id,
                "file_id": file_id,
                "analyze_command": f'tencent-doc-review analyze --doc-id "{file_id}" --output report.md',
            }
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        items = await doc_client.list_documents(folder_id or "")
        if output_format == "json":
            payload = [
                {
                    "file_id": item.file_id,
                    "title": item.title,
                    "type": item.doc_type,
                    "url": item.url,
                }
                for item in items
            ]
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        if not items:
            click.echo("No files returned.")
            return

        click.echo("file_id\ttype\ttitle")
        for item in items:
            click.echo(f"{item.file_id}\t{item.doc_type or '-'}\t{item.title or '-'}")
    finally:
        await doc_client.close()


async def _skill_run(
    doc_id: str,
    title: str,
    target_folder_id: str,
    target_space_id: str,
    target_space_type: str,
    target_path: str,
    download_dir: str,
    mcp_client_name: Optional[str],
    bridge_executable: str,
    bridge_args: str,
    provider: str,
    debug_dir: str,
) -> None:
    settings = reload_settings()
    client = _create_skill_mcp_client(
        client_name=mcp_client_name or settings.skill_mcp_client,
        settings=settings,
        bridge_executable=bridge_executable,
        bridge_args=bridge_args,
    )

    request = SkillRequest(
        source_document=TencentDocReference(doc_id=doc_id, title=title),
        target_location=UploadTarget(
            folder_id=target_folder_id,
            space_id=target_space_id,
            space_type=target_space_type,
            path_hint=target_path,
            display_name=target_path or target_folder_id,
        ),
        download_directory=download_dir,
        debug_output_dir=get_effective_debug_output_dir(debug_dir or settings.review_debug_output_dir),
        llm_provider=provider or settings.llm_provider,
    )
    try:
        response = await SkillPipeline().run(client, request)
    except MCPBridgeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(asdict(response), ensure_ascii=False, indent=2, default=str))


class _MockMCPClient:
    async def export_document(self, reference, download_format):
        return MCPDownloadPayload(
            reference=reference,
            format=download_format,
            filename=f"{reference.doc_id}.docx",
            text_content=(
                "一、产品概述\n"
                "Skill workflow placeholder content includes realistic body text so the review pipeline can run in tests. "
                "It describes product workflow, collaboration model, and output characteristics in enough detail.\n"
                "二、结论与推荐建议\n"
                "The report recommends further evaluation and a structured comparison against competing products."
            ),
            metadata={"source": "cli-skill-placeholder"},
        )

    async def upload_document(self, local_path, target, remote_filename):
        return MCPUploadPayload(
            target=target,
            uploaded_name=remote_filename,
            remote_file_id="mock-remote-file-id",
            remote_url=f"https://docs.qq.com/mock/{remote_filename}",
            metadata={"source": "cli-skill-placeholder"},
        )


def _create_skill_mcp_client(
    client_name: str,
    settings,
    bridge_executable: str = "",
    bridge_args: str = "",
) -> object:
    normalized_name = client_name.strip().lower()
    if normalized_name == "mock":
        return _MockMCPClient()
    if normalized_name == "openclaw":
        executable = bridge_executable or settings.openclaw_mcp_bridge_executable or _detect_python_executable()
        args_text = bridge_args or settings.openclaw_mcp_bridge_args
        if not executable:
            raise click.UsageError(
                "Unable to determine how to start the OpenClaw bridge. "
                "Please set OPENCLAW_MCP_BRIDGE_EXECUTABLE or pass --bridge-executable."
            )
        if not args_text:
            openclaw_executable = _detect_openclaw_executable()
            if not openclaw_executable:
                raise click.UsageError(
                    "Unable to locate the OpenClaw executable automatically. "
                    "Please make sure openclaw/openclaw.cmd is in PATH, or set OPENCLAW_MCP_BRIDGE_ARGS "
                    "or pass --bridge-args explicitly."
                )
            bridge_script = _default_openclaw_bridge_script()
            if not bridge_script.exists():
                raise click.UsageError(f"OpenClaw bridge script not found: {bridge_script}")
            args_text = _build_default_openclaw_bridge_args_text(openclaw_executable)
        return CommandMCPClient(
            build_bridge_config(
                client_name="openclaw",
                executable=executable,
                args_text=args_text,
                timeout_seconds=settings.mcp_bridge_timeout,
                env={"TENCENT_DOCS_TOKEN": settings.tencent_docs_token} if settings.tencent_docs_token else {},
            )
        )
    if normalized_name == "claude_code":
        executable = bridge_executable or settings.claude_code_mcp_bridge_executable
        args_text = bridge_args or settings.claude_code_mcp_bridge_args
        if not executable:
            raise click.UsageError("CLAUDE_CODE_MCP_BRIDGE_EXECUTABLE is required for --mcp-client claude_code.")
        return CommandMCPClient(
            build_bridge_config(
                client_name="claude_code",
                executable=executable,
                args_text=args_text,
                timeout_seconds=settings.mcp_bridge_timeout,
                env={"TENCENT_DOCS_TOKEN": settings.tencent_docs_token} if settings.tencent_docs_token else {},
            )
        )
    raise click.UsageError(f"Unsupported MCP client: {client_name}")
