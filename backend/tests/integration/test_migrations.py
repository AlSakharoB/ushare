from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from receiptsplit.config import Settings
from receiptsplit.db.session import build_engine

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("previous", [None, "0001"])
def test_empty_and_previous_database_migration(previous: str | None) -> None:
    engine = build_engine(Settings().database_url)
    # PostgreSQL transactional DDL: no existing schema or user data is touched.
    schema = "rs_migration_test_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            if previous:
                command.upgrade(config, previous)
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
            assert connection.scalar(text("SELECT to_regclass('item_shares')")) is not None
        finally:
            transaction.rollback()
