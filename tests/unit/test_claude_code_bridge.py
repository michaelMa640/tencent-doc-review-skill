import json

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
