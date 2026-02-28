from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.

    Import your model modules before calling ``Base.metadata.create_all``
    or running Alembic autogenerate so the metadata is populated.
    """
