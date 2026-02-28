from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from libs.db.models import Base


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql+psycopg://sentient:sentient@127.0.0.1:5432/sentient")


engine = create_engine(get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
