"""Lazy SQLAlchemy session factory for retrieval and atomic chat writes."""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    from app.config import settings

    url = make_url(settings.database_url.get_secret_value())
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)
