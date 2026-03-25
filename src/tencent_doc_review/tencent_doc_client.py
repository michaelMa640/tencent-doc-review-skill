"""Tencent Docs client models and a minimal document-read integration layer."""

from __future__ import annotations

import asyncio
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


class TencentDocError(RuntimeError):
    """Base error for Tencent Docs integration failures."""


class TencentDocAuthError(TencentDocError):
    """Authentication or authorization failure."""


class TencentDocRateLimitError(TencentDocError):
    """Tencent Docs API rate limit failure."""


class TencentDocRequestError(TencentDocError):
    """Unexpected Tencent Docs request failure."""


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
        max_retries: int = 2,
        retry_delay: float = 1.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.access_token = access_token
        self.client_id = client_id
        self.open_id = open_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = client
        self._owns_client = client is None

    async def get_document_info(self, file_id: str) -> DocumentInfo:
        payload = await self._request_json("GET", f"/drive/v2/files/{file_id}/metadata")
        info = payload.get("file") or payload.get("data") or payload
        return DocumentInfo(
            file_id=file_id,
            title=info.get("title", "") or info.get("name", ""),
            doc_type=info.get("type", "doc"),
            create_time=info.get("create_time", ""),
            modify_time=info.get("modify_time", ""),
            url=info.get("url"),
        )

    async def get_document_content(self, file_id: str) -> str:
        data = await self._request_json("GET", f"/doc/v3/{file_id}")
        document = self._extract_document_payload(data)
        return self._extract_text(document)

    async def get_document_bundle(self, file_id: str) -> tuple[DocumentInfo, str]:
        info_task = asyncio.create_task(self.get_document_info(file_id))
        content_task = asyncio.create_task(self.get_document_content(file_id))
        info, content = await asyncio.gather(info_task, content_task)
        if not info.title:
            info.title = file_id
        return info, content

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

    async def update_document_content(self, file_id: str, content: str) -> Dict[str, Any]:
        payload = {
            "content": content,
        }
        data = await self._request_json("PUT", f"/doc/v3/{file_id}", json_body=payload)
        return {
            "success": True,
            "mode": "replace",
            "file_id": file_id,
            "response": data,
        }

    async def append_review_block(self, file_id: str, block_markdown: str) -> Dict[str, Any]:
        info, existing_content = await self.get_document_bundle(file_id)
        separator = "\n\n" if existing_content.strip() else ""
        updated_content = f"{existing_content.rstrip()}{separator}{block_markdown.strip()}\n"
        result = await self.update_document_content(file_id, updated_content)
        result["title"] = info.title
        result["appended"] = True
        return result

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

    async def _request_json(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_configured()
        if httpx is None:
            raise ModuleNotFoundError("httpx is required to call the Tencent Docs API")

        client = self._get_client()
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                    json=json_body,
                )
                self._raise_for_status(response)
                return response.json()
            except (TencentDocRateLimitError, TencentDocRequestError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_delay * (attempt + 1))
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        if isinstance(last_error, TencentDocError):
            raise last_error
        raise TencentDocRequestError(f"Failed to request Tencent Docs API: {last_error}")

    def _raise_for_status(self, response: Any) -> None:
        status_code = getattr(response, "status_code", 0)
        if 200 <= status_code < 300:
            return
        if status_code in {401, 403}:
            raise TencentDocAuthError(f"Tencent Docs auth failed with status {status_code}")
        if status_code == 429:
            raise TencentDocRateLimitError("Tencent Docs API rate limited the request")
        raise TencentDocRequestError(f"Tencent Docs request failed with status {status_code}")

    def _extract_document_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(payload.get("document"), dict):
            return payload["document"]
        if isinstance(payload.get("data"), dict):
            data = payload["data"]
            if isinstance(data.get("document"), dict):
                return data["document"]
        return payload

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
