"""Tencent Docs client models and a minimal document-read integration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - fallback for lean environments
    httpx = None


@dataclass
class DocumentInfo:
    file_id: str
    title: str = ""
    doc_type: str = "doc"
    create_time: str = ""
    modify_time: str = ""
    url: Optional[str] = None


@dataclass
class Comment:
    content: str
    position: Dict[str, Any] = field(default_factory=dict)
    quote_text: Optional[str] = None
    comment_type: str = "text"


class TencentDocClient:
    """Minimal OpenAPI client.

    The current implementation focuses on read access and leaves comment writeback
    as a compatibility no-op until the repository adopts a confirmed writeback flow.
    """

    def __init__(
        self,
        access_token: str = "",
        client_id: str = "",
        open_id: str = "",
        base_url: str = "https://docs.qq.com/openapi",
        timeout: int = 30,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.access_token = access_token
        self.client_id = client_id
        self.open_id = open_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def get_document_content(self, file_id: str) -> str:
        self._ensure_configured()
        if httpx is None:
            raise ModuleNotFoundError("httpx is required to call the Tencent Docs API")
        client = self._get_client()
        response = await client.get(
            f"{self.base_url}/doc/v3/{file_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()
        return self._extract_text(data.get("document") or {})

    async def list_documents(self, folder_id: str) -> List[DocumentInfo]:
        raise NotImplementedError(
            "Folder listing is not implemented yet. Wire this to the official file APIs before using it."
        )

    async def add_comment(self, file_id: str, comment: Comment) -> bool:
        result = await self.add_comments_batch(file_id, [comment])
        return bool(result.get("success"))

    async def add_comments_batch(self, file_id: str, comments: List[Comment]) -> Dict[str, Any]:
        return {
            "success": False,
            "mode": "noop",
            "file_id": file_id,
            "count": len(comments),
            "message": "Comment writeback is not enabled in this repository yet.",
        }

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    def _ensure_configured(self) -> None:
        if not self.access_token:
            raise ValueError("TENCENT_DOCS_TOKEN is not configured")
        if not self.client_id:
            raise ValueError("TENCENT_DOCS_CLIENT_ID is not configured")
        if not self.open_id:
            raise ValueError("TENCENT_DOCS_OPEN_ID is not configured")

    def _headers(self) -> Dict[str, str]:
        return {
            "Access-Token": self.access_token,
            "Client-Id": self.client_id,
            "Open-Id": self.open_id,
            "Accept": "application/json",
        }

    def _get_client(self) -> httpx.AsyncClient:
        if httpx is None:
            raise ModuleNotFoundError("httpx is required to call the Tencent Docs API")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _extract_text(self, node: Dict[str, Any]) -> str:
        chunks: List[str] = []
        self._walk_node(node, chunks)
        text = "".join(chunks)
        return "\n".join(line.rstrip() for line in text.splitlines()).strip()

    def _walk_node(self, node: Dict[str, Any], chunks: List[str]) -> None:
        text = node.get("text")
        if isinstance(text, str):
            chunks.append(text)
            if node.get("type") == "Paragraph":
                chunks.append("\n")

        for child in node.get("children") or []:
            if isinstance(child, dict):
                self._walk_node(child, chunks)


TencentDocMCPClient = TencentDocClient
