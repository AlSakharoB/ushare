from alembic import context

from receiptsplit.config import Settings
from receiptsplit.db import (
    auth_models,  # noqa: F401
    member_models,  # noqa: F401
    receipt_models,  # noqa: F401
)
from receiptsplit.db.session import Base, build_engine

config = context.config
target_metadata = Base.metadata


def run_migrations() -> None:
    if context.is_offline_mode():
        context.configure(
            url=Settings().database_url, target_metadata=target_metadata, literal_binds=True
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        provided = config.attributes.get("connection")
        if provided is not None:
            context.configure(connection=provided, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
            return
        with build_engine(Settings().database_url).connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()


run_migrations()
