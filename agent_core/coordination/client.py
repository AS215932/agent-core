"""Async, signed client for the agent-core coordination service."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import BaseModel

from agent_core.contracts.coordination import (
    ApprovalRecord,
    CaseProjection,
    HandoffEnvelope,
    HandoffRecord,
    HandoffResult,
    LoopHeartbeat,
    VerificationResult,
)
from agent_core.coordination.auth import LoopRequestSigner


class CoordinatorError(RuntimeError):
    """Coordinator request failed or returned an invalid response."""


def _json_bytes(value: BaseModel | dict[str, Any] | None) -> bytes:
    if value is None:
        return b""
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class CoordinatorClient:
    def __init__(
        self,
        base_url: str,
        *,
        signer: LoopRequestSigner,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.signer = signer
        self.timeout = timeout
        self.transport = transport

    @classmethod
    def from_env(cls, loop_id: str, *, prefix: str = "HYRULE_COORDINATOR") -> CoordinatorClient:
        base_url = os.environ.get(f"{prefix}_URL", "").strip()
        key_id = os.environ.get(f"{prefix}_KEY_ID", "default").strip()
        secret = os.environ.get(f"{prefix}_SECRET", "").strip()
        if not base_url or not secret:
            raise CoordinatorError(f"{prefix}_URL and {prefix}_SECRET are required")
        return cls(
            base_url,
            signer=LoopRequestSigner(loop_id=loop_id, key_id=key_id, secret=secret),
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: BaseModel | dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        body = _json_bytes(payload)
        headers = self.signer.headers(method=method, path=path, body=body)
        if body:
            headers["Content-Type"] = "application/json"
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            response = await client.request(
                method,
                path,
                content=body or None,
                params=params,
                headers=headers,
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise CoordinatorError(
                f"coordinator {method} {path} returned {response.status_code}: {detail}"
            )
        if not response.content:
            return None
        return response.json()

    async def health(self) -> dict[str, Any]:
        return dict(await self._request("GET", "/healthz"))

    async def loops(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/v1/loops")
        return list(data.get("loops", []))

    async def heartbeat(self, heartbeat: LoopHeartbeat) -> dict[str, Any]:
        return dict(
            await self._request(
                "POST", f"/v1/loops/{heartbeat.loop_id}/heartbeat", payload=heartbeat
            )
        )

    async def put_case(self, projection: CaseProjection) -> CaseProjection:
        data = await self._request(
            "PUT", f"/v1/cases/{projection.case_id}", payload=projection
        )
        return CaseProjection.model_validate(data)

    async def cases(self, **filters: Any) -> list[CaseProjection]:
        data = await self._request("GET", "/v1/cases", params=filters)
        return [CaseProjection.model_validate(item) for item in data.get("cases", [])]

    async def case(self, case_id: str) -> CaseProjection:
        return CaseProjection.model_validate(
            await self._request("GET", f"/v1/cases/{case_id}")
        )

    async def create_handoff(self, envelope: HandoffEnvelope) -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request("POST", "/v1/handoffs", payload=envelope)
        )

    async def handoff(self, handoff_id: str) -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request("GET", f"/v1/handoffs/{handoff_id}")
        )

    async def handoffs(self, **filters: Any) -> list[HandoffRecord]:
        data = await self._request("GET", "/v1/handoffs", params=filters)
        return [HandoffRecord.model_validate(item) for item in data.get("handoffs", [])]

    async def handoff_events(self, handoff_id: str) -> list[dict[str, Any]]:
        data = await self._request("GET", f"/v1/handoffs/{handoff_id}/events")
        return list(data.get("events", []))

    async def inbox(self, *, status: str | None = None, limit: int = 100) -> list[HandoffRecord]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        data = await self._request("GET", "/v1/inbox", params=params)
        return [HandoffRecord.model_validate(item) for item in data.get("handoffs", [])]

    async def claim(self, handoff_id: str, *, lease_seconds: int = 120) -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request(
                "POST",
                f"/v1/handoffs/{handoff_id}/claim",
                payload={"lease_seconds": lease_seconds},
            )
        )

    async def heartbeat_claim(self, handoff_id: str, *, lease_seconds: int = 120) -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request(
                "POST",
                f"/v1/handoffs/{handoff_id}/heartbeat",
                payload={"lease_seconds": lease_seconds},
            )
        )

    async def progress(self, handoff_id: str, summary: str) -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request(
                "POST", f"/v1/handoffs/{handoff_id}/progress", payload={"summary": summary}
            )
        )

    async def submit_result(self, result: HandoffResult) -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request(
                "POST", f"/v1/handoffs/{result.handoff_id}/result", payload=result
            )
        )

    async def verify(self, result: VerificationResult) -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request(
                "POST", f"/v1/handoffs/{result.handoff_id}/verify", payload=result
            )
        )

    async def approve(self, record: ApprovalRecord) -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request(
                "POST", f"/v1/approvals/{record.handoff_id}/decision", payload=record
            )
        )

    async def approvals(self, *, status: str = "awaiting_approval") -> list[HandoffRecord]:
        data = await self._request("GET", "/v1/approvals", params={"status": status})
        return [HandoffRecord.model_validate(item) for item in data.get("handoffs", [])]

    async def cancel(self, handoff_id: str, reason: str = "") -> HandoffRecord:
        return HandoffRecord.model_validate(
            await self._request(
                "POST", f"/v1/handoffs/{handoff_id}/cancel", payload={"reason": reason}
            )
        )
