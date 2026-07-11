"""Transactional storage for the LHP-v2 coordinator."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent_core.contracts._base import utcnow
from agent_core.contracts.coordination import (
    ApprovalRecord,
    CaseProjection,
    HandoffEnvelope,
    HandoffEvent,
    HandoffRecord,
    HandoffResult,
    HandoffStatus,
    LoopHeartbeat,
    LoopRegistration,
    VerificationResult,
    default_lease_expiry,
)

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./coordinator.db"


def database_url() -> str:
    return os.environ.get("HYRULE_COORDINATOR_DATABASE_URL", DEFAULT_DATABASE_URL)


class Base(DeclarativeBase):
    pass


class LoopRow(Base):
    __tablename__ = "coordination_loops"

    loop_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    registration: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    summary: Mapped[str] = mapped_column(Text, default="")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class CaseRow(Base):
    __tablename__ = "coordination_cases"

    case_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    owner_loop: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(80), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    projection: Mapped[dict[str, Any]] = mapped_column(JSON)


class HandoffRow(Base):
    __tablename__ = "coordination_handoffs"

    handoff_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    source_loop: Mapped[str] = mapped_column(String(64), index=True)
    target_loop: Mapped[str] = mapped_column(String(64), index=True)
    capability: Mapped[str] = mapped_column(String(160), index=True)
    case_id: Mapped[str] = mapped_column(String(180), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    scope_hash: Mapped[str] = mapped_column(String(64), index=True)
    claim_owner: Mapped[str] = mapped_column(String(64), default="")
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    envelope: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    verification: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    approval: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class HandoffEventRow(Base):
    __tablename__ = "coordination_handoff_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(180), unique=True)
    handoff_id: Mapped[str] = mapped_column(String(180), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str] = mapped_column(String(180), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event: Mapped[dict[str, Any]] = mapped_column(JSON)


class IdempotencyRow(Base):
    __tablename__ = "coordination_idempotency"
    __table_args__ = (UniqueConstraint("source_loop", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_loop: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    handoff_id: Mapped[str] = mapped_column(String(180), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NonceRow(Base):
    __tablename__ = "coordination_nonces"
    __table_args__ = (UniqueConstraint("loop_id", "nonce"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loop_id: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[str] = mapped_column(String(180))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OutboxRow(Base):
    __tablename__ = "coordination_trace_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(180), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str] = mapped_column(Text, default="")


def make_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(url or database_url(), future=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class CoordinatorStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessionmaker

    async def register_nonce(self, loop_id: str, nonce: str, observed_at: datetime) -> bool:
        async with self.sessions() as session:
            session.add(NonceRow(loop_id=loop_id, nonce=nonce, observed_at=observed_at))
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    async def seed_loops(self, registrations: list[LoopRegistration]) -> None:
        async with self.sessions() as session, session.begin():
            for registration in registrations:
                row = await session.get(LoopRow, registration.loop_id)
                payload = registration.model_dump(mode="json")
                if row is None:
                    session.add(
                        LoopRow(
                            loop_id=registration.loop_id,
                            registration=payload,
                            status="disabled" if not registration.enabled else "unknown",
                            summary="",
                        )
                    )
                else:
                    row.registration = payload

    async def loops(self) -> list[dict[str, Any]]:
        async with self.sessions() as session:
            rows = (await session.execute(select(LoopRow).order_by(LoopRow.loop_id))).scalars()
            return [
                {
                    **row.registration,
                    "status": row.status,
                    "summary": row.summary,
                    "last_heartbeat_at": _aware(row.last_heartbeat_at),
                    "heartbeat": row.heartbeat,
                }
                for row in rows
            ]

    async def heartbeat(self, heartbeat: LoopHeartbeat) -> dict[str, Any]:
        async with self.sessions() as session, session.begin():
            row = await session.get(LoopRow, heartbeat.loop_id)
            if row is None:
                raise KeyError("loop is not registered")
            row.status = heartbeat.status
            row.summary = heartbeat.summary
            row.last_heartbeat_at = heartbeat.observed_at
            row.heartbeat = heartbeat.model_dump(mode="json")
            return {**row.registration, **heartbeat.model_dump(mode="json")}

    async def put_case(self, projection: CaseProjection) -> CaseProjection:
        async with self.sessions() as session, session.begin():
            row = await session.get(CaseRow, projection.case_id, with_for_update=True)
            if row is not None:
                if row.owner_loop != projection.owner_loop:
                    raise PermissionError("case owner cannot change")
                if projection.version < row.version:
                    raise ValueError("stale case projection version")
                row.version = projection.version
                row.status = projection.status
                row.updated_at = projection.updated_at
                row.projection = projection.model_dump(mode="json")
            else:
                session.add(
                    CaseRow(
                        case_id=projection.case_id,
                        owner_loop=projection.owner_loop,
                        version=projection.version,
                        status=projection.status,
                        updated_at=projection.updated_at,
                        projection=projection.model_dump(mode="json"),
                    )
                )
            return projection

    async def cases(
        self, *, owner_loop: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[CaseProjection]:
        statement = select(CaseRow)
        if owner_loop:
            statement = statement.where(CaseRow.owner_loop == owner_loop)
        if status:
            statement = statement.where(CaseRow.status == status)
        statement = statement.order_by(CaseRow.updated_at.desc()).limit(max(1, min(limit, 500)))
        async with self.sessions() as session:
            rows = (await session.execute(statement)).scalars()
            return [CaseProjection.model_validate(row.projection) for row in rows]

    async def case(self, case_id: str) -> CaseProjection | None:
        async with self.sessions() as session:
            row = await session.get(CaseRow, case_id)
            return CaseProjection.model_validate(row.projection) if row else None

    async def create_handoff(self, envelope: HandoffEnvelope) -> HandoffRecord:
        async with self.sessions() as session, session.begin():
            existing_id = (
                await session.execute(
                    select(IdempotencyRow.handoff_id).where(
                        IdempotencyRow.source_loop == envelope.source_loop,
                        IdempotencyRow.idempotency_key == envelope.idempotency_key,
                    )
                )
            ).scalar_one_or_none()
            if existing_id:
                row = await session.get(HandoffRow, existing_id)
                if row is None:
                    raise RuntimeError("idempotency record references a missing handoff")
                return self._record(row)
            if await session.get(HandoffRow, envelope.handoff_id) is not None:
                raise ValueError("handoff_id already exists")
            status: HandoffStatus = (
                "queued" if envelope.approval_tier == "none" else "awaiting_approval"
            )
            now = utcnow()
            row = HandoffRow(
                handoff_id=envelope.handoff_id,
                source_loop=envelope.source_loop,
                target_loop=envelope.target_loop,
                capability=envelope.capability,
                case_id=envelope.case_id,
                status=status,
                version=1,
                scope_hash=envelope.scope_hash,
                claim_owner="",
                envelope=envelope.model_dump(mode="json"),
                created_at=envelope.created_at,
                updated_at=now,
                expires_at=envelope.expires_at,
            )
            session.add(row)
            session.add(
                IdempotencyRow(
                    source_loop=envelope.source_loop,
                    idempotency_key=envelope.idempotency_key,
                    handoff_id=envelope.handoff_id,
                    created_at=now,
                )
            )
            self._add_event(
                session,
                row,
                event_type="created",
                actor_id=envelope.source_loop,
                actor_loop=envelope.source_loop,
                from_status=None,
                summary=envelope.summary,
            )
            if status == "awaiting_approval":
                self._add_event(
                    session,
                    row,
                    event_type="approval_requested",
                    actor_id="coordinator",
                    actor_loop="",
                    from_status=status,
                    summary=f"{envelope.approval_tier} approval required",
                )
            return self._record(row)

    async def handoff(self, handoff_id: str) -> HandoffRecord | None:
        async with self.sessions() as session:
            row = await session.get(HandoffRow, handoff_id)
            return self._record(row) if row else None

    async def handoffs(
        self,
        *,
        source_loop: str | None = None,
        target_loop: str | None = None,
        status: str | None = None,
        case_id: str | None = None,
        limit: int = 100,
    ) -> list[HandoffRecord]:
        statement = select(HandoffRow)
        if source_loop:
            statement = statement.where(HandoffRow.source_loop == source_loop)
        if target_loop:
            statement = statement.where(HandoffRow.target_loop == target_loop)
        if status:
            statement = statement.where(HandoffRow.status == status)
        if case_id:
            statement = statement.where(HandoffRow.case_id == case_id)
        statement = statement.order_by(HandoffRow.updated_at.desc()).limit(max(1, min(limit, 500)))
        async with self.sessions() as session:
            rows = (await session.execute(statement)).scalars()
            return [self._record(row) for row in rows]

    async def events(self, handoff_id: str) -> list[HandoffEvent]:
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    select(HandoffEventRow)
                    .where(HandoffEventRow.handoff_id == handoff_id)
                    .order_by(HandoffEventRow.id)
                )
            ).scalars()
            return [HandoffEvent.model_validate(row.event) for row in rows]

    async def outbox_batch(self, limit: int = 100) -> list[tuple[int, dict[str, Any]]]:
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    select(OutboxRow)
                    .where(OutboxRow.delivered_at.is_(None))
                    .order_by(OutboxRow.id)
                    .limit(max(1, min(limit, 500)))
                )
            ).scalars()
            return [(row.id, dict(row.payload)) for row in rows]

    async def mark_outbox(self, row_id: int, *, error: str = "") -> None:
        async with self.sessions() as session, session.begin():
            row = await session.get(OutboxRow, row_id, with_for_update=True)
            if row is None:
                return
            if error:
                row.last_error = error[:1000]
            else:
                row.delivered_at = utcnow()
                row.last_error = ""

    async def approve(self, handoff_id: str, approval: ApprovalRecord) -> HandoffRecord:
        async with self.sessions() as session, session.begin():
            row = await self._locked(session, handoff_id)
            if row.status != "awaiting_approval":
                raise ValueError("handoff is not awaiting approval")
            if approval.handoff_id != row.handoff_id or approval.scope_hash != row.scope_hash:
                raise ValueError("approval does not match the handoff scope")
            envelope = HandoffEnvelope.model_validate(row.envelope)
            if envelope.approval_tier == "senior" and approval.approver_role != "senior":
                raise PermissionError("senior approval is required")
            if approval.expires_at and approval.expires_at <= utcnow():
                raise ValueError("approval has expired")
            previous = row.status
            row.approval = approval.model_dump(mode="json")
            row.status = "queued" if approval.decision == "approved" else "rejected"
            self._touch(row)
            self._add_event(
                session,
                row,
                event_type="approved" if approval.decision == "approved" else "rejected",
                actor_id=approval.approver_id,
                actor_loop="observatory",
                from_status=previous,
                summary=approval.rationale,
            )
            return self._record(row)

    async def claim(self, handoff_id: str, actor_loop: str, lease_seconds: int) -> HandoffRecord:
        async with self.sessions() as session, session.begin():
            row = await self._locked(session, handoff_id)
            now = utcnow()
            aware_lease = _aware(row.lease_expires_at)
            lease_expired = aware_lease is not None and aware_lease <= now
            if row.status not in {"queued", "claimed", "in_progress"}:
                raise ValueError("handoff is not claimable")
            if row.status != "queued" and not lease_expired and row.claim_owner != actor_loop:
                raise ValueError("handoff is leased by another worker")
            previous = row.status
            row.status = "claimed"
            row.claim_owner = actor_loop
            row.lease_expires_at = default_lease_expiry(lease_seconds)
            self._touch(row)
            self._add_event(
                session,
                row,
                event_type="claimed",
                actor_id=actor_loop,
                actor_loop=actor_loop,
                from_status=previous,
                summary="handoff claimed",
            )
            return self._record(row)

    async def heartbeat_claim(
        self, handoff_id: str, actor_loop: str, lease_seconds: int
    ) -> HandoffRecord:
        async with self.sessions() as session, session.begin():
            row = await self._locked(session, handoff_id)
            if row.claim_owner != actor_loop or row.status not in {"claimed", "in_progress"}:
                raise PermissionError("loop does not own the active claim")
            row.lease_expires_at = default_lease_expiry(lease_seconds)
            self._touch(row)
            self._add_event(
                session,
                row,
                event_type="heartbeat",
                actor_id=actor_loop,
                actor_loop=actor_loop,
                from_status=row.status,
                summary="claim lease extended",
            )
            return self._record(row)

    async def progress(self, handoff_id: str, actor_loop: str, summary: str) -> HandoffRecord:
        async with self.sessions() as session, session.begin():
            row = await self._locked(session, handoff_id)
            if row.claim_owner != actor_loop or row.status not in {"claimed", "in_progress"}:
                raise PermissionError("loop does not own the active claim")
            previous = row.status
            row.status = "in_progress"
            self._touch(row)
            self._add_event(
                session,
                row,
                event_type="progress",
                actor_id=actor_loop,
                actor_loop=actor_loop,
                from_status=previous,
                summary=summary,
            )
            return self._record(row)

    async def submit_result(
        self, handoff_id: str, actor_loop: str, result: HandoffResult
    ) -> HandoffRecord:
        async with self.sessions() as session, session.begin():
            row = await self._locked(session, handoff_id)
            if row.claim_owner != actor_loop or row.status not in {"claimed", "in_progress"}:
                raise PermissionError("loop does not own the active claim")
            if result.handoff_id != handoff_id:
                raise ValueError("result handoff_id mismatch")
            previous = row.status
            row.result = result.model_dump(mode="json")
            row.lease_expires_at = None
            row.status = (
                "failed"
                if result.outcome in {"failed", "rejected"}
                else "result_submitted"
            )
            self._touch(row)
            self._add_event(
                session,
                row,
                event_type="failed" if row.status == "failed" else "result_submitted",
                actor_id=actor_loop,
                actor_loop=actor_loop,
                from_status=previous,
                summary=result.summary,
            )
            return self._record(row)

    async def verify(
        self, handoff_id: str, actor_loop: str, verification: VerificationResult
    ) -> HandoffRecord:
        async with self.sessions() as session, session.begin():
            row = await self._locked(session, handoff_id)
            if row.source_loop != actor_loop:
                raise PermissionError("only the source loop may verify a handoff")
            if row.status not in {"result_submitted", "verification_pending"}:
                raise ValueError("handoff has no result awaiting verification")
            if verification.handoff_id != handoff_id:
                raise ValueError("verification handoff_id mismatch")
            previous = row.status
            row.verification = verification.model_dump(mode="json")
            if verification.verdict == "pending":
                row.status = "verification_pending"
                event_type = "verification_pending"
            elif verification.verdict == "passed":
                row.status = "completed"
                event_type = "verified"
            else:
                row.status = "failed"
                event_type = "failed"
            self._touch(row)
            self._add_event(
                session,
                row,
                event_type=event_type,
                actor_id=actor_loop,
                actor_loop=actor_loop,
                from_status=previous,
                summary=verification.summary,
            )
            return self._record(row)

    async def cancel(self, handoff_id: str, actor_id: str, reason: str) -> HandoffRecord:
        async with self.sessions() as session, session.begin():
            row = await self._locked(session, handoff_id)
            if row.status in {"completed", "rejected", "failed", "cancelled", "expired"}:
                raise ValueError("terminal handoff cannot be cancelled")
            previous = row.status
            row.status = "cancelled"
            row.lease_expires_at = None
            self._touch(row)
            self._add_event(
                session,
                row,
                event_type="cancelled",
                actor_id=actor_id,
                actor_loop=actor_id if actor_id != "observatory" else "",
                from_status=previous,
                summary=reason,
            )
            return self._record(row)

    async def _locked(self, session: AsyncSession, handoff_id: str) -> HandoffRow:
        row = (
            await session.execute(
                select(HandoffRow)
                .where(HandoffRow.handoff_id == handoff_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise KeyError("handoff not found")
        return row

    @staticmethod
    def _touch(row: HandoffRow) -> None:
        row.version += 1
        row.updated_at = utcnow()

    @staticmethod
    def _record(row: HandoffRow) -> HandoffRecord:
        return HandoffRecord(
            envelope=HandoffEnvelope.model_validate(row.envelope),
            status=row.status,  # type: ignore[arg-type]
            version=row.version,
            claim_owner=row.claim_owner,
            lease_expires_at=_aware(row.lease_expires_at),
            result=HandoffResult.model_validate(row.result) if row.result else None,
            verification=(
                VerificationResult.model_validate(row.verification) if row.verification else None
            ),
            approval=ApprovalRecord.model_validate(row.approval) if row.approval else None,
            updated_at=_aware(row.updated_at) or utcnow(),
        )

    @staticmethod
    def _add_event(
        session: AsyncSession,
        row: HandoffRow,
        *,
        event_type: str,
        actor_id: str,
        actor_loop: str,
        from_status: str | None,
        summary: str,
    ) -> None:
        event = HandoffEvent(
            handoff_id=row.handoff_id,
            event_type=event_type,  # type: ignore[arg-type]
            actor_id=actor_id,
            actor_loop=actor_loop,
            from_status=from_status,  # type: ignore[arg-type]
            to_status=row.status,  # type: ignore[arg-type]
            handoff_version=row.version,
            summary=summary,
        )
        session.add(
            HandoffEventRow(
                event_id=event.event_id,
                handoff_id=row.handoff_id,
                event_type=event.event_type,
                actor_id=event.actor_id,
                created_at=event.created_at,
                event=event.model_dump(mode="json"),
            )
        )
        session.add(
            OutboxRow(
                event_id=event.event_id,
                payload={
                    "event_type": "handoff_transition",
                    "summary": event.summary or f"{row.handoff_id}: {event.event_type}",
                    "handoff_id": row.handoff_id,
                    "case_id": row.case_id,
                    "payload": {
                        "handoff_event": event.model_dump(mode="json"),
                        "source_loop": row.source_loop,
                        "target_loop": row.target_loop,
                        "capability": row.capability,
                    },
                },
                created_at=event.created_at,
            )
        )
