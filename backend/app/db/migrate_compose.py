"""Wait for the Docker Compose database, then apply Alembic migrations."""

from __future__ import annotations

import time

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings


def main() -> None:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    for attempt in range(30):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            break
        except OperationalError:
            if attempt == 29:
                raise
            time.sleep(1)
    command.upgrade(Config("alembic.ini"), "head")


if __name__ == "__main__":
    main()