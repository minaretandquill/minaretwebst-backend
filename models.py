"""SQLAlchemy ORM models — the whole Minaret & Quill House schema."""
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "mq_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class Book(Base):
    __tablename__ = "mq_books"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    author: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    author_slug: Mapped[str] = mapped_column(String(160), default="", nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Multi-format Amazon links
    amazon_paperback: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    amazon_hardcover: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    amazon_ebook: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    amazon_link: Mapped[str] = mapped_column(String(1024), default="", nullable=False)  # legacy

    imprint: Mapped[str] = mapped_column(String(32), default="main", nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    price: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    published_date: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="available", nullable=False, index=True)
    expected_date: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    sample_pdf_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class Announcement(Base):
    __tablename__ = "mq_announcements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    cta_label: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    cta_link: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class Subscriber(Base):
    __tablename__ = "mq_subscribers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class BookInterest(Base):
    __tablename__ = "mq_book_interests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    book_id: Mapped[str] = mapped_column(String(36), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    __table_args__ = (
        UniqueConstraint("book_id", "email", name="uq_book_email"),
        Index("ix_bi_book", "book_id"),
    )


class Author(Base):
    __tablename__ = "mq_authors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class Review(Base):
    __tablename__ = "mq_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    book_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


# Helper: turn ORM row → plain dict with ISO datetimes (for API responses)
def to_dict(obj) -> dict:
    d = {}
    for c in obj.__table__.columns:
        v = getattr(obj, c.name)
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            v = v.isoformat()
        d[c.name] = v
    # Never leak password hashes
    d.pop("password_hash", None)
    return d
