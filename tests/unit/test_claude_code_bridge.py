import json
from pathlib import Path

import pytest

from tencent_doc_review.access.claude_code_bridge import (
    ClaudeCodeBridgeError,
    extract_agent_json,
    extract_claude_result_text,
)


def test_extract_claude_result_text_reads_json_result_field():
    payload = {"type": "result", "subtype": "success", "result": '{"ok":true}'}
    assert extract_claude_result_text(json.dumps(payload)) == '{"ok":true}'


def test_extract_agent_json_accepts_code_fenced_json():
    text = '```json\n{"uploaded_name":"file.docx"}\n```'
    assert extract_agent_json(text) == {"uploaded_name": "file.docx"}


def test_extract_claude_result_text_rejects_missing_result_text():
    with pytest.raises(ClaudeCodeBridgeError):
        extract_claude_result_text(json.dumps({"type": "result"}))


def test_upload_prompt_mentions_target_parent_id_for_space_folder_nodes():
    source = Path(__file__).resolve().parents[2] / "src" / "tencent_doc_review" / "access" / "claude_code_bridge.py"
    text = source.read_text(encoding="utf-8")
    assert "target_parent_id=" in text
    assert "Do not pass folder_id to manage.move_file_to_space" in text
    assert "manage.pre_import does not accept folder_id" in text
