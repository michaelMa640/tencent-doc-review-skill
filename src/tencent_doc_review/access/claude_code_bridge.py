"""Claude Code-specific MCP bridge built on top of Claude Code headless mode."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class ClaudeCodeBridgeSettings:
    """Runtime settings for the Claude Code bridge process."""

    claude_executable: str = "claude"
    model: str = ""
    permission_mode: str = "acceptEdits"
    cwd: str = ""
    timeout_seconds: int = 180
    dangerously_skip_permissions: bool = False


class ClaudeCodeBridgeError(RuntimeError):
    """Raised when the Claude Code bridge cannot complete a request."""


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Tencent Docs MCP actions through Claude Code CLI.")
    parser.add_argument("--claude-executable", default="claude")
    parser.add_argument("--model", default="")
    parser.add_argument("--permission-mode", default="acceptEdits")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dangerously-skip-permissions", action="store_true")
    args = parser.parse_args()

    settings = ClaudeCodeBridgeSettings(
        claude_executable=args.claude_executable,
        model=args.model,
        permission_mode=args.permission_mode,
        cwd=args.cwd,
        timeout_seconds=args.timeout,
        dangerously_skip_permissions=args.dangerously_skip_permissions,
    )

    try:
        request = json.loads(sys.stdin.read())
        result = handle_request(settings, request)
        sys.stdout.write(json.dumps({"success": True, "result": result}, ensure_ascii=False))
        return 0
    except Exception as exc:  # pragma: no cover - integration path
        sys.stdout.write(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def handle_request(settings: ClaudeCodeBridgeSettings, request: Dict[str, Any]) -> Dict[str, Any]:
    action = request.get("action")
    payload = request.get("payload", {})
    if action == "export_document":
        return export_document(settings, payload)
    if action == "upload_document":
        return upload_document(settings, payload)
    raise ClaudeCodeBridgeError(f"Unsupported action: {action}")


def export_document(settings: ClaudeCodeBridgeSettings, payload: Dict[str, Any]) -> Dict[str, Any]:
    reference = payload.get("reference", {})
    preferred_download_dir = str(reference.get("metadata", {}).get("preferred_download_dir", "")).strip()
    prompt = build_export_prompt(reference, preferred_download_dir)
    response_text = run_claude(settings, prompt)
    payload_json = extract_agent_json(response_text)
    if "error" in payload_json:
        raise ClaudeCodeBridgeError(payload_json["error"])

    source_path = str(payload_json.get("source_path", "")).strip()
    text_content = str(payload_json.get("text_content", "")).strip()
    filename = payload_json.get("filename") or f"{reference.get('doc_id', 'document')}.docx"
    metadata = dict(payload_json.get("metadata", {}))
    metadata.setdefault("bridge_mode", "download" if source_path else "text_fallback")
    metadata.setdefault("source", "claude_code")
    if source_path:
        metadata["source_path"] = source_path
    if preferred_download_dir:
        metadata["preferred_download_dir"] = preferred_download_dir

    return {
        "filename": filename,
        "format": payload_json.get("format", "docx"),
        "source_path": source_path or None,
        "text_content": text_content,
        "metadata": metadata,
    }


def upload_document(settings: ClaudeCodeBridgeSettings, payload: Dict[str, Any]) -> Dict[str, Any]:
    target = payload.get("target", {})
    local_path = Path(payload["local_path"])
    remote_filename = str(payload.get("remote_filename", "")).strip()
    folder_id = str(target.get("folder_id", "")).strip()
    target_parent_hint = folder_id.split("$", 1)[1] if "$" in folder_id else folder_id
    prompt = (
        "You are acting as a bridge for a Tencent Docs review skill running through Claude Code. "
        "Upload the local Word document to the requested Tencent Docs destination using the configured Tencent Docs MCP. "
        f"Target space_type={target.get('space_type','')}, space_id={target.get('space_id','')}, "
        f"folder_id={folder_id}, path_hint={target.get('path_hint','')}. "
        f"Local file path={local_path}. Required final visible document title={remote_filename}. "
        "Important Tencent Docs MCP constraints: "
        "manage.pre_import does not accept folder_id, so do not rely on pre_import to place the file into a folder. "
        "If the destination is a team/workspace node, upload/import first, then move the imported file with "
        f"manage.move_file_to_space using space_id={target.get('space_id','')} and target_parent_id={target_parent_hint}. "
        "Do not pass folder_id to manage.move_file_to_space; that tool expects target_parent_id. "
        "If the initial upload uses a temporary or local filename, rename or move the uploaded document so the final visible title exactly matches the required title. "
        "After upload/move/rename, verify by listing the exact target folder or node and confirm the new file is visible there before returning success. "
        "Do not explain. Do not use markdown code fences. "
        'Return exactly one JSON object on success: {"uploaded_name":"final_visible_uploaded_filename","remote_file_id":"remote_file_id","remote_url":"remote_url","metadata":{"source":"claude_code","mode":"upload"}}. '
        'On failure return exactly: {"error":"error_message"}.'
    )
    response_text = run_claude(settings, prompt)
    payload_json = extract_agent_json(response_text)
    if "error" in payload_json:
        raise ClaudeCodeBridgeError(payload_json["error"])
    return {
        "uploaded_name": payload_json.get("uploaded_name") or remote_filename or local_path.name,
        "remote_file_id": payload_json.get("remote_file_id", ""),
        "remote_url": payload_json.get("remote_url", ""),
        "metadata": dict(payload_json.get("metadata", {})),
    }


def build_export_prompt(reference: Dict[str, Any], preferred_download_dir: str) -> str:
    doc_id = reference.get("doc_id", "")
    title = reference.get("title", "")
    parts = [
        "You are acting as a bridge for a Tencent Docs review skill running through Claude Code.",
        "First, use Tencent Docs MCP to download the target Tencent document as a docx file.",
        f"Target document title: {title}.",
        f"Supplementary identifier if needed: {doc_id}.",
    ]
    if preferred_download_dir:
        parts.append(f"Save the downloaded file to exactly this local directory: {preferred_download_dir}.")
    parts.append(
        'If direct docx download succeeds, return exactly one JSON object: {"filename":"downloaded_filename","format":"docx","source_path":"absolute_local_path","metadata":{"source":"claude_code","mode":"download"}}.'
    )
    parts.append(
        'If direct download is unavailable, fall back to reading the document text and return: {"filename":"fallback.docx","format":"docx","text_content":"plain_text_content","metadata":{"source":"claude_code","mode":"text_fallback"}}.'
    )
    parts.append('If both fail, return exactly: {"error":"error_message"}.')
    parts.append("Do not explain. Do not use markdown code fences. Do not call web search.")
    return " ".join(parts)


def run_claude(settings: ClaudeCodeBridgeSettings, prompt: str) -> str:
    command = [settings.claude_executable, "-p", prompt, "--output-format", "json"]
    if settings.permission_mode:
        command.extend(["--permission-mode", settings.permission_mode])
    if settings.cwd:
        command.extend(["--cwd", settings.cwd])
    if settings.model:
        command.extend(["--model", settings.model])
    if settings.dangerously_skip_permissions:
        command.append("--dangerously-skip-permissions")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PYTHONIOENCODING": "utf-8", **os.environ},
        timeout=settings.timeout_seconds,
    )
    if completed.returncode != 0:
        raise ClaudeCodeBridgeError(completed.stderr.strip() or completed.stdout.strip() or "Claude Code command failed")
    return extract_claude_result_text(completed.stdout)


def extract_claude_result_text(stdout: str) -> str:
    text = stdout.strip()
    if not text:
        raise ClaudeCodeBridgeError("Claude Code returned empty output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, str) and result.strip():
            return result.strip()
        text_value = payload.get("text")
        if isinstance(text_value, str) and text_value.strip():
            return text_value.strip()
    raise ClaudeCodeBridgeError("Claude Code JSON output had no final result text")


def extract_agent_json(text: str) -> Dict[str, Any]:
    cleaned = strip_code_fences(text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return extract_first_json_object(cleaned)


def strip_code_fences(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return text


def extract_first_json_object(text: str) -> Dict[str, Any]:
    start = text.find("{")
    if start == -1:
        raise ClaudeCodeBridgeError("No JSON object found in Claude Code output")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])
    raise ClaudeCodeBridgeError("Unterminated JSON object in Claude Code output")


if __name__ == "__main__":
    raise SystemExit(main())
