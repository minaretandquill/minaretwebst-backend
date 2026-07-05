"""Minaret & Quill House API — FastAPI + SQLAlchemy (async) + MariaDB/MySQL."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, response
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from database import Base, engine, SessionLocal, get_session
from models import User, Book, Announcement, Subscriber, BookInterest, Author, Review, to_dict
from seed import seed_defaults


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"].lower()
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="Minaret & Quill House API")
@app.head("/")
async def health_head():
    return Response(status_code=200)
@app.get("/")
async def root_get():
    return {"ok": True, "name": "Minaret & Quill House API"}
    

api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(email: str) -> str:
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_admin(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = payload.get("sub")
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return to_dict(user)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
Imprint = Literal["main", "kids"]
BookStatus = Literal["available", "coming_soon"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


class BookCreate(BaseModel):
    title: str
    subtitle: Optional[str] = ""
    author: Optional[str] = ""
    author_slug: Optional[str] = ""
    description: str
    cover_image: str
    amazon_paperback: Optional[str] = ""
    amazon_hardcover: Optional[str] = ""
    amazon_ebook: Optional[str] = ""
    amazon_link: Optional[str] = ""
    imprint: Imprint = "main"
    category: Optional[str] = ""
    price: Optional[str] = ""
    pages: Optional[int] = None
    is_featured: bool = False
    published_date: Optional[str] = ""
    status: BookStatus = "available"
    expected_date: Optional[str] = ""
    sample_pdf_url: Optional[str] = ""


class BookUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    author: Optional[str] = None
    author_slug: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    amazon_paperback: Optional[str] = None
    amazon_hardcover: Optional[str] = None
    amazon_ebook: Optional[str] = None
    amazon_link: Optional[str] = None
    imprint: Optional[Imprint] = None
    category: Optional[str] = None
    price: Optional[str] = None
    pages: Optional[int] = None
    is_featured: Optional[bool] = None
    published_date: Optional[str] = None
    status: Optional[BookStatus] = None
    expected_date: Optional[str] = None
    sample_pdf_url: Optional[str] = None


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    cta_label: Optional[str] = ""
    cta_link: Optional[str] = ""
    is_active: bool = True


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    cta_label: Optional[str] = None
    cta_link: Optional[str] = None
    is_active: Optional[bool] = None


class SubscribeRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = ""


class InterestRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = ""


class AuthorCreate(BaseModel):
    name: str
    slug: str
    role: Optional[str] = ""
    bio: str
    photo_url: Optional[str] = ""


class AuthorUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    role: Optional[str] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None


class ReviewCreate(BaseModel):
    book_id: str
    name: str = Field(min_length=1, max_length=120)
    location: Optional[str] = Field(default="", max_length=120)
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=10, max_length=2000)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@api_router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    email = payload.email.lower()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(email)
    return TokenResponse(access_token=token, email=email)


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_admin)):
    return user


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------
@api_router.get("/books")
async def list_books(
    imprint: Optional[Imprint] = None,
    featured: Optional[bool] = None,
    status: Optional[BookStatus] = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Book).order_by(Book.created_at.desc())
    filters = []
    if imprint:
        filters.append(Book.imprint == imprint)
    if featured is not None:
        filters.append(Book.is_featured == featured)
    if status:
        filters.append(Book.status == status)
    if filters:
        stmt = stmt.where(and_(*filters))
    rows = (await session.execute(stmt)).scalars().all()
    return [to_dict(b) for b in rows]


@api_router.get("/books/{book_id}")
async def get_book(book_id: str, session: AsyncSession = Depends(get_session)):
    b = (await session.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Book not found")
    return to_dict(b)


@api_router.post("/books")
async def create_book(payload: BookCreate, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    data = payload.model_dump()
    b = Book(id=str(uuid.uuid4()), **data)
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return to_dict(b)


@api_router.put("/books/{book_id}")
async def update_book(book_id: str, payload: BookUpdate, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    b = (await session.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Book not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    for k, v in updates.items():
        setattr(b, k, v)
    await session.commit()
    await session.refresh(b)
    return to_dict(b)


@api_router.delete("/books/{book_id}")
async def delete_book(book_id: str, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    result = await session.execute(delete(Book).where(Book.id == book_id))
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------
@api_router.get("/announcements")
async def list_announcements(active_only: bool = False, session: AsyncSession = Depends(get_session)):
    stmt = select(Announcement).order_by(Announcement.created_at.desc())
    if active_only:
        stmt = stmt.where(Announcement.is_active.is_(True))
    rows = (await session.execute(stmt)).scalars().all()
    return [to_dict(a) for a in rows]


@api_router.post("/announcements")
async def create_announcement(payload: AnnouncementCreate, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    a = Announcement(id=str(uuid.uuid4()), **payload.model_dump())
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return to_dict(a)


@api_router.put("/announcements/{ann_id}")
async def update_announcement(ann_id: str, payload: AnnouncementUpdate, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    a = (await session.execute(select(Announcement).where(Announcement.id == ann_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    for k, v in updates.items():
        setattr(a, k, v)
    await session.commit()
    await session.refresh(a)
    return to_dict(a)


@api_router.delete("/announcements/{ann_id}")
async def delete_announcement(ann_id: str, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    result = await session.execute(delete(Announcement).where(Announcement.id == ann_id))
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Newsletter
# ---------------------------------------------------------------------------
@api_router.post("/newsletter/subscribe")
async def subscribe(payload: SubscribeRequest, session: AsyncSession = Depends(get_session)):
    email = payload.email.lower()
    existing = (await session.execute(select(Subscriber).where(Subscriber.email == email))).scalar_one_or_none()
    if existing:
        return {"ok": True, "message": "You're already subscribed."}
    s = Subscriber(id=str(uuid.uuid4()), email=email, name=payload.name or "")
    session.add(s)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return {"ok": True, "message": "You're already subscribed."}
    return {"ok": True, "message": "Thank you for subscribing."}


@api_router.get("/newsletter/subscribers")
async def list_subscribers(session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    rows = (await session.execute(select(Subscriber).order_by(Subscriber.created_at.desc()))).scalars().all()
    return [to_dict(s) for s in rows]


@api_router.delete("/newsletter/subscribers/{sub_id}")
async def delete_subscriber(sub_id: str, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    result = await session.execute(delete(Subscriber).where(Subscriber.id == sub_id))
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Book interest (Notify Me)
# ---------------------------------------------------------------------------
@api_router.post("/books/{book_id}/interest")
async def register_interest(book_id: str, payload: InterestRequest, session: AsyncSession = Depends(get_session)):
    book = (await session.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    email = payload.email.lower()
    existing = (await session.execute(
        select(BookInterest).where(and_(BookInterest.book_id == book_id, BookInterest.email == email))
    )).scalar_one_or_none()
    if existing:
        return {"ok": True, "message": "You're already on the list."}
    session.add(BookInterest(id=str(uuid.uuid4()), book_id=book_id, email=email, name=payload.name or ""))
    # Add to general newsletter too (best-effort)
    sub_exists = (await session.execute(select(Subscriber).where(Subscriber.email == email))).scalar_one_or_none()
    if not sub_exists:
        session.add(Subscriber(id=str(uuid.uuid4()), email=email, name=payload.name or ""))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return {"ok": True, "message": "You're already on the list."}
    return {"ok": True, "message": "We'll let you know the moment it's available."}


@api_router.get("/books/{book_id}/interest-count")
async def interest_count(book_id: str, session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(BookInterest).where(BookInterest.book_id == book_id))).scalars().all()
    return {"book_id": book_id, "count": len(rows)}


@api_router.get("/books/{book_id}/interests")
async def list_interests(book_id: str, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    rows = (await session.execute(
        select(BookInterest).where(BookInterest.book_id == book_id).order_by(BookInterest.created_at.desc())
    )).scalars().all()
    return [to_dict(i) for i in rows]


@api_router.delete("/books/{book_id}/interests/{interest_id}")
async def delete_interest(book_id: str, interest_id: str, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    result = await session.execute(
        delete(BookInterest).where(and_(BookInterest.id == interest_id, BookInterest.book_id == book_id))
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Interest not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------
@api_router.get("/authors")
async def list_authors(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Author).order_by(Author.name.asc()))).scalars().all()
    return [to_dict(a) for a in rows]


@api_router.get("/authors/{slug}")
async def get_author(slug: str, session: AsyncSession = Depends(get_session)):
    a = (await session.execute(select(Author).where(Author.slug == slug))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Author not found")
    return to_dict(a)


@api_router.post("/authors")
async def create_author(payload: AuthorCreate, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    existing = (await session.execute(select(Author).where(Author.slug == payload.slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")
    a = Author(id=str(uuid.uuid4()), **payload.model_dump())
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return to_dict(a)


@api_router.put("/authors/{author_id}")
async def update_author(author_id: str, payload: AuthorUpdate, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    a = (await session.execute(select(Author).where(Author.id == author_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Author not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    for k, v in updates.items():
        setattr(a, k, v)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Slug already exists")
    await session.refresh(a)
    return to_dict(a)


@api_router.delete("/authors/{author_id}")
async def delete_author(author_id: str, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    result = await session.execute(delete(Author).where(Author.id == author_id))
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Author not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@api_router.post("/reviews")
async def submit_review(payload: ReviewCreate, session: AsyncSession = Depends(get_session)):
    book = (await session.execute(select(Book).where(Book.id == payload.book_id))).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    r = Review(id=str(uuid.uuid4()), is_published=False, **payload.model_dump())
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return to_dict(r)


@api_router.get("/books/{book_id}/reviews")
async def list_book_reviews(book_id: str, session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(Review).where(and_(Review.book_id == book_id, Review.is_published.is_(True)))
        .order_by(Review.created_at.desc())
    )).scalars().all()
    return [to_dict(r) for r in rows]


@api_router.get("/reviews")
async def list_reviews(published: Optional[bool] = None, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    stmt = select(Review).order_by(Review.created_at.desc())
    if published is not None:
        stmt = stmt.where(Review.is_published == published)
    rows = (await session.execute(stmt)).scalars().all()
    return [to_dict(r) for r in rows]


@api_router.put("/reviews/{review_id}/approve")
async def approve_review(review_id: str, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    r = (await session.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    r.is_published = True
    await session.commit()
    await session.refresh(r)
    return to_dict(r)


@api_router.delete("/reviews/{review_id}")
async def delete_review(review_id: str, session: AsyncSession = Depends(get_session), user: dict = Depends(get_current_admin)):
    result = await session.execute(delete(Review).where(Review.id == review_id))
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root():
    return {"name": "Minaret & Quill House API", "ok": True}


@api_router.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(select(1))
    return {"ok": True, "db": "connected"}


# ---------------------------------------------------------------------------
# Startup: create tables + seed admin + placeholder content
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await seed_defaults(session, ADMIN_EMAIL, ADMIN_PASSWORD, hash_password, verify_password)
    logger.info("Startup complete — tables ensured, seed applied.")


@app.on_event("shutdown")
async def on_shutdown():
    await engine.dispose()


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
