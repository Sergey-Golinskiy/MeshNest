"""Bootstrap script: create the first admin account.

Usage (inside api container):
    python -m app.scripts.create_admin <email> [<password>]

Если password не указан — генерируется случайный 16-символьный и печатается в stdout.
"""
from __future__ import annotations

import asyncio
import secrets
import sys

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.db import SessionLocal
from app.models import User
from app.models._types import UserRole


async def _main(email: str, password: str | None) -> int:
    if password is None:
        password = secrets.token_urlsafe(12)
        generated = True
    else:
        generated = False

    async with SessionLocal() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"ERROR: user {email} already exists.", file=sys.stderr)
            return 2

        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.admin,
            display_name="Admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()

    print(f"Admin created: {email}")
    if generated:
        print(f"Generated password: {password}")
        print("Сохраните пароль — он больше не будет показан.")
    return 0


def main() -> None:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(__doc__)
        sys.exit(1)
    email = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) == 3 else None
    code = asyncio.run(_main(email, password))
    sys.exit(code)


if __name__ == "__main__":
    main()
