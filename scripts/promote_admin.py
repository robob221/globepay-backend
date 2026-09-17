"""One-off operator script: grant/revoke admin access for a user by phone
number. There is deliberately no HTTP endpoint that can do this - the only
way to create the platform's first admin (or any admin) is for whoever
operates the database to run this directly.

Usage:
    python -m scripts.promote_admin +233200000001
    python -m scripts.promote_admin +233200000001 --revoke
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import select  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from src.auth.models import User  # noqa: E402
from src.db.main import engine  # noqa: E402


async def main(phone_number: str, revoke: bool) -> None:
    async with AsyncSession(engine) as session:
        result = await session.exec(select(User).where(User.phone_number == phone_number))
        user = result.first()
        if user is None:
            print(f"No user found with phone number {phone_number}")
            return

        user.is_admin = not revoke
        session.add(user)
        await session.commit()
        action = "revoked from" if revoke else "granted to"
        print(f"Admin access {action} {user.full_name} ({user.phone_number})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phone_number")
    parser.add_argument("--revoke", action="store_true", help="Remove admin access instead of granting it")
    args = parser.parse_args()
    asyncio.run(main(args.phone_number, args.revoke))
