import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Column, Identity
from sqlmodel import Field, SQLModel

from src.common.db_types import tz_aware_column


class AdminAuditLog(SQLModel, table=True):
    """One row per state-changing admin action - who did what, to which
    record, and when. Read-only admin endpoints (listing users, viewing
    stats) aren't logged here; only actions that actually change something
    a customer or support conversation could later ask about."""

    __tablename__ = "admin_audit_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    admin_user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    action: str  # e.g. "suspend_user", "refund_crossborder_transfer"
    target_type: str  # e.g. "user", "crossborder_transfer", "card", "card_funding"
    target_id: uuid.UUID = Field(index=True)
    details: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    # A DB-generated identity, used only for ordering - two actions taken
    # milliseconds apart (e.g. suspend then immediately reactivate in one
    # request flow) can land on the same created_at microsecond, and
    # "ORDER BY created_at DESC" alone has no deterministic tiebreak for
    # ties. An audit log that can't reliably show *which* happened first
    # defeats its own purpose, so true insertion order needs its own column
    # rather than trusting wall-clock precision.
    seq: int | None = Field(default=None, sa_column=Column(BigInteger, Identity(), nullable=False, unique=True))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=tz_aware_column())
