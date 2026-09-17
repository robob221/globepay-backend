"""Shared column helpers.

Postgres columns for `datetime` fields default to TIMESTAMP WITHOUT TIME
ZONE unless told otherwise, which then rejects the timezone-aware UTC
datetimes this codebase inserts everywhere. Every timestamp column must
use this helper (or an equivalent explicit `DateTime(timezone=True)`)
instead of a bare `datetime` type annotation.
"""

from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum


def tz_aware_column(nullable: bool = False) -> Column:
    return Column(DateTime(timezone=True), nullable=nullable)


def named_enum_column(enum_cls: type[PyEnum], pg_type_name: str, nullable: bool = False) -> Column:
    """SQLAlchemy names a Postgres native enum type after the Python class
    by default - two unrelated enums that happen to share a class name
    (e.g. a module-local `ContributionStatus`) silently collide into one
    shared Postgres type, built from whichever gets created first, and
    reject the other's members. Always pass an explicit, globally-unique
    pg_type_name for any enum column."""
    return Column(SAEnum(enum_cls, name=pg_type_name), nullable=nullable)
