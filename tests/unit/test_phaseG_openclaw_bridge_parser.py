import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.access.openclaw_bridge import (
    OpenClawBridgeError,
    build_export_prompt,
    extract_agent_json,
    extract_first_json_object,
    extract_openclaw_payload,
)


class PhaseGOpenClawBridgeParserTests(unittest.TestCase):
    def test_extract_first_json_object_skips_prefix_and_suffix_logs(self):
        raw = (
            "[plugins] registered tool\n"
            '{"payloads":[{"text":"{\\"ok\\":true,\\"value\\":\\"demo\\"}","mediaUrl":null}],"meta":{"durationMs":1}}\n'
            "[agent] done\n"
        )
        parsed = extract_first_json_object(raw)
        self.assertIn("payloads", parsed)
        self.assertEqual(parsed["meta"]["durationMs"], 1)

    def test_extract_openclaw_payload_returns_first_text_payload(self):
        raw = (
            '[plugins] ready\n'
            '{"runId":"abc","status":"ok","result":{"payloads":[{"text":"{\\"uploaded_name\\":\\"demo.docx\\",\\"remote_file_id\\":\\"id-1\\"}","mediaUrl":null}],"meta":{}}}\n'
        )
        payload = extract_openclaw_payload(raw)
        self.assertIn("uploaded_name", payload["text"])

    def test_extract_agent_json_accepts_source_path_payload(self):
        response = {
            "text": '{"filename":"demo.docx","source_path":"C:/Users/VBTvisitor/Desktop/test/demo.docx","metadata":{"source":"openclaw","mode":"download"}}'
        }
        payload = extract_agent_json(response)
        self.assertEqual(payload["filename"], "demo.docx")
        self.assertEqual(payload["metadata"]["mode"], "download")

    def test_extract_agent_json_rejects_connection_error(self):
        with self.assertRaises(OpenClawBridgeError):
            extract_agent_json({"text": "Connection error."})

    def test_build_export_prompt_prefers_download_and_mentions_fallback(self):
        prompt = build_export_prompt({"doc_id": "DU123", "title": "Demo"}, "C:/Users/VBTvisitor/Desktop/test")
        self.assertIn("First, use Tencent Docs MCP to download the target document as a docx file", prompt)
        self.assertIn("source_path", prompt)
        self.assertIn("text_fallback", prompt)
        self.assertIn("C:/Users/VBTvisitor/Desktop/test", prompt)


if __name__ == "__main__":
    unittest.main()
