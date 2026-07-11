"""Per-loop request signing for coordinator HTTP traffic."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime


def body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def signature_message(
    *, method: str, path: str, timestamp: str, nonce: str, key_id: str, body: bytes
) -> bytes:
    return "\n".join(
        [method.upper(), path, timestamp, nonce, key_id, body_digest(body)]
    ).encode("utf-8")


def build_signature(
    *,
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    key_id: str,
    body: bytes,
) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        signature_message(
            method=method,
            path=path,
            timestamp=timestamp,
            nonce=nonce,
            key_id=key_id,
            body=body,
        ),
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True)
class LoopRequestSigner:
    loop_id: str
    key_id: str
    secret: str

    def headers(self, *, method: str, path: str, body: bytes = b"") -> dict[str, str]:
        timestamp = datetime.now(UTC).isoformat()
        nonce = secrets.token_urlsafe(24)
        return {
            "X-Agent-Loop-Identity": self.loop_id,
            "X-Agent-Loop-Key-Id": self.key_id,
            "X-Agent-Loop-Timestamp": timestamp,
            "X-Agent-Loop-Nonce": nonce,
            "X-Agent-Loop-Signature": build_signature(
                secret=self.secret,
                method=method,
                path=path,
                timestamp=timestamp,
                nonce=nonce,
                key_id=self.key_id,
                body=body,
            ),
        }
