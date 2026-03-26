import json
import sys
from pathlib import Path


def main() -> int:
    request = json.loads(sys.stdin.read())
    action = request.get("action")
    payload = request.get("payload", {})

    if action == "export_document":
        reference = payload.get("reference", {})
        result = {
            "format": payload.get("download_format", "docx"),
            "filename": f"{reference.get('doc_id', 'document')}.docx",
            "text_content": "Mock bridge正文第一段\n\nMock bridge正文第二段",
            "metadata": {
                "bridge_client": request.get("client"),
                "bridge_action": action,
            },
        }
        sys.stdout.write(json.dumps({"success": True, "result": result}, ensure_ascii=False))
        return 0

    if action == "upload_document":
        local_path = Path(payload["local_path"])
        result = {
            "uploaded_name": payload.get("remote_filename") or local_path.name,
            "remote_file_id": "bridge-remote-file-id",
            "remote_url": f"https://docs.qq.com/mock/{payload.get('remote_filename') or local_path.name}",
            "metadata": {
                "bridge_client": request.get("client"),
                "bridge_action": action,
                "received_bytes": local_path.stat().st_size,
                "target_space_type": payload.get("target", {}).get("space_type", ""),
            },
        }
        sys.stdout.write(json.dumps({"success": True, "result": result}, ensure_ascii=False))
        return 0

    sys.stdout.write(json.dumps({"success": False, "error": f"unsupported action: {action}"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
