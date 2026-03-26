"""OpenClaw-specific MCP bridge built on top of the OpenClaw CLI."""

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
class OpenClawBridgeSettings:
    """Runtime settings for the OpenClaw bridge process."""

    openclaw_executable: str = "openclaw.cmd"
    agent_id: str = "main"
    profile: str = ""
    local: bool = True
    thinking: str = "minimal"
    timeout_seconds: int = 180


class OpenClawBridgeError(RuntimeError):
    """Raised when the OpenClaw bridge cannot complete a request."""


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Tencent Docs MCP actions through OpenClaw CLI.")
    parser.add_argument("--openclaw-executable", default="openclaw.cmd")
    parser.add_argument("--agent-id", default="main")
    parser.add_argument("--profile", default="")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--thinking", default="minimal")
    parser.add_argument("--no-local", action="store_true")
    args = parser.parse_args()

    settings = OpenClawBridgeSettings(
        openclaw_executable=args.openclaw_executable,
        agent_id=args.agent_id,
        profile=args.profile,
        local=not args.no_local,
        thinking=args.thinking,
        timeout_seconds=args.timeout,
    )

    try:
        request = json.loads(sys.stdin.read())
        result = handle_request(settings, request)
        sys.stdout.write(json.dumps({"success": True, "result": result}, ensure_ascii=False))
        return 0
    except Exception as exc:  # pragma: no cover - integration path
        sys.stdout.write(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def handle_request(settings: OpenClawBridgeSettings, request: Dict[str, Any]) -> Dict[str, Any]:
    action = request.get("action")
    payload = request.get("payload", {})
    if action == "export_document":
        return export_document(settings, payload)
    if action == "upload_document":
        return upload_document(settings, payload)
    raise OpenClawBridgeError(f"Unsupported action: {action}")


def export_document(settings: OpenClawBridgeSettings, payload: Dict[str, Any]) -> Dict[str, Any]:
    reference = payload.get("reference", {})
    preferred_download_dir = str(reference.get("metadata", {}).get("preferred_download_dir", "")).strip()
    prompt = build_export_prompt(reference, preferred_download_dir)
    response = run_openclaw(settings, prompt)
    payload_json = extract_agent_json(response)
    if "error" in payload_json:
        raise OpenClawBridgeError(payload_json["error"])

    source_path = str(payload_json.get("source_path", "")).strip()
    text_content = str(payload_json.get("text_content", "")).strip()
    filename = payload_json.get("filename") or f"{reference.get('doc_id', 'document')}.docx"
    metadata = dict(payload_json.get("metadata", {}))
    metadata.setdefault("bridge_mode", "download" if source_path else "text_fallback")
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


def upload_document(settings: OpenClawBridgeSettings, payload: Dict[str, Any]) -> Dict[str, Any]:
    target = payload.get("target", {})
    local_path = Path(payload["local_path"])
    prompt = (
        "You are acting as a bridge for a Tencent Docs review skill. "
        "Upload the local Word document to the requested Tencent Docs destination. "
        f"Target space_type={target.get('space_type','')}, space_id={target.get('space_id','')}, "
        f"folder_id={target.get('folder_id','')}, path_hint={target.get('path_hint','')}. "
        f"Local file path={local_path}. Remote filename={payload.get('remote_filename','')}. "
        "Do not explain. Do not use markdown code fences. "
        'Return exactly one JSON object on success: {"uploaded_name":"uploaded_filename","remote_file_id":"remote_file_id","remote_url":"remote_url","metadata":{"source":"openclaw","mode":"upload"}}. '
        'On failure return exactly: {"error":"error_message"}.'
    )
    response = run_openclaw(settings, prompt)
    payload_json = extract_agent_json(response)
    if "error" in payload_json:
        raise OpenClawBridgeError(payload_json["error"])
    return {
        "uploaded_name": payload_json.get("uploaded_name") or payload.get("remote_filename") or local_path.name,
        "remote_file_id": payload_json.get("remote_file_id", ""),
        "remote_url": payload_json.get("remote_url", ""),
        "metadata": dict(payload_json.get("metadata", {})),
    }


def build_export_prompt(reference: Dict[str, Any], preferred_download_dir: str) -> str:
    doc_id = reference.get("doc_id", "")
    title = reference.get("title", "")
    parts = [
        "You are acting as a bridge for a Tencent Docs review skill.",
        "First, use Tencent Docs MCP to download the target Tencent document as a docx file.",
        f"Target document title: {title}.",
        f"Supplementary identifier if needed: {doc_id}.",
    ]
    if preferred_download_dir:
        parts.append(f"Save the downloaded file to exactly this local directory: {preferred_download_dir}.")
    parts.append(
        'If direct docx download succeeds, return exactly one JSON object: {"filename":"downloaded_filename","format":"docx","source_path":"absolute_local_path","metadata":{"source":"openclaw","mode":"download"}}.'
    )
    parts.append(
        'If direct download is unavailable, fall back to reading the document text and return: {"filename":"fallback.docx","format":"docx","text_content":"plain_text_content","metadata":{"source":"openclaw","mode":"text_fallback"}}.'
    )
    parts.append('If both fail, return exactly: {"error":"error_message"}.')
    parts.append("Do not explain. Do not use markdown code fences. Do not call web search.")
    return " ".join(parts)


def run_openclaw(settings: OpenClawBridgeSettings, prompt: str) -> Dict[str, Any]:
    executable = settings.openclaw_executable
    command = [executable]
    if settings.profile:
        command.extend(["--profile", settings.profile])
    command.extend(
        [
            "agent",
            "--agent",
            settings.agent_id,
            "--json",
            "--thinking",
            settings.thinking,
            "--timeout",
            str(settings.timeout_seconds),
            "--message",
            prompt,
        ]
    )
    if settings.local:
        command.append("--local")
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        command = ["cmd", "/c", *command]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PYTHONIOENCODING": "utf-8", **os.environ},
    )
    if completed.returncode != 0:
        raise OpenClawBridgeError(completed.stderr.strip() or completed.stdout.strip() or "OpenClaw command failed")
    return extract_openclaw_payload(completed.stdout)


def extract_openclaw_payload(stdout: str) -> Dict[str, Any]:
    outer = extract_first_json_object(stdout)
    payloads = outer.get("payloads") or outer.get("result", {}).get("payloads") or []
    if not payloads:
        raise OpenClawBridgeError("OpenClaw returned no payloads")
    text = payloads[0].get("text", "")
    if not text:
        raise OpenClawBridgeError("OpenClaw payload had no text response")
    return {"text": text, "outer": outer}


def extract_agent_json(response: Dict[str, Any]) -> Dict[str, Any]:
    text = response.get("text", "").strip()
    if text == "Connection error.":
        raise OpenClawBridgeError("OpenClaw agent returned Connection error.")
    cleaned = strip_code_fences(text)
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
        raise OpenClawBridgeError("No JSON object found in OpenClaw output")
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
    raise OpenClawBridgeError("Unterminated JSON object in OpenClaw output")


if __name__ == "__main__":
    raise SystemExit(main())
