from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.persistence.database import create_database_engine


def migration(connection, direction, revision):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = connection
    getattr(command, direction)(config, revision)


async def in_schema(url, check):
    engine = create_database_engine(url)
    schema = "test_" + uuid4().hex
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET search_path TO "{schema}"'))
            await connection.commit()
            try:
                await connection.run_sync(migration, "upgrade", "head")
                await connection.commit()
                await check(connection)
            finally:
                await connection.rollback()
                await connection.execute(text("SET search_path TO public"))
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                await connection.commit()
    finally:
        await engine.dispose()


