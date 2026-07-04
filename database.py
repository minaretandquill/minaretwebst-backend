"""SQLAlchemy async engine + session setup for MariaDB/MySQL."""
import os
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DB_URL = URL.create(
    drivername="mysql+aiomysql",
    username=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.environ.get("DB_PORT", 3306)),
    database=os.environ["DB_NAME"],
    query={"charset": "utf8mb4"},
)

engine = create_async_engine(
    DB_URL,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
