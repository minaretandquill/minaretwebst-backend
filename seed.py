"""Seed the admin user + placeholder books/announcements on first run."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Book, Announcement


PLACEHOLDER_BOOKS = [
    {
        "title": "The Sacred Heart",
        "subtitle": "A Journey of Inner Purification",
        "author": "Minaret & Quill",
        "description": "A contemplative work on the spiritual diseases of the heart and the path to nearness with Allah. Drawing from the rich tradition of tazkiyah, this book invites the reader to a sustained inner journey of refinement and remembrance.",
        "cover_image": "https://images.pexels.com/photos/4079272/pexels-photo-4079272.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "amazon_paperback": "https://www.amazon.com/",
        "imprint": "main",
        "category": "Spiritual Transformation",
        "price": "$24.99",
        "pages": 248,
        "is_featured": True,
        "published_date": "2025",
        "status": "available",
    },
    {
        "title": "By the Pen",
        "subtitle": "Reflections on Surah al-Qalam",
        "author": "Minaret & Quill",
        "description": "An illuminated study of the Qur'anic oath upon the pen, drawing the reader through verses of wisdom, knowledge, and the sacredness of the written word.",
        "cover_image": "https://images.pexels.com/photos/5517168/pexels-photo-5517168.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "amazon_paperback": "https://www.amazon.com/",
        "imprint": "main",
        "category": "Tafsir & Qur'an",
        "price": "$22.00",
        "pages": 196,
        "is_featured": True,
        "published_date": "2025",
        "status": "available",
    },
    {
        "title": "Men of Light",
        "subtitle": "Stories of the Friends of Allah",
        "author": "Minaret & Quill",
        "description": "A collection of luminous accounts from the lives of those whose hearts were turned wholly to their Lord. Stories that remind, ignite, and elevate.",
        "cover_image": "https://images.unsplash.com/photo-1606326608606-aa0b62935f2b?auto=format&fit=crop&w=940&q=80",
        "amazon_paperback": "https://www.amazon.com/",
        "imprint": "main",
        "category": "Friends of Allah",
        "price": "$28.00",
        "pages": 312,
        "is_featured": True,
        "published_date": "2025",
        "status": "available",
    },
    {
        "title": "My First Names of Allah",
        "subtitle": "A Mini Muslim Series Book",
        "author": "The Mini Muslim Series",
        "description": "An imaginative introduction to the Beautiful Names of Allah for young hearts. Soft illustrations and gentle words guide little ones to their first remembrance.",
        "cover_image": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=940&q=80",
        "amazon_paperback": "https://www.amazon.com/",
        "imprint": "kids",
        "category": "Children",
        "price": "$16.99",
        "pages": 32,
        "is_featured": True,
        "published_date": "2025",
        "status": "available",
    },
    {
        "title": "Little Prophets, Big Lessons",
        "subtitle": "A Mini Muslim Series Book",
        "author": "The Mini Muslim Series",
        "description": "A child's first encounter with the Prophets — peace be upon them all — through stories that plant seeds of wonder and sincere love.",
        "cover_image": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=940&q=80",
        "amazon_paperback": "https://www.amazon.com/",
        "imprint": "kids",
        "category": "Children",
        "price": "$18.99",
        "pages": 40,
        "is_featured": False,
        "published_date": "2025",
        "status": "available",
    },
    {
        "title": "The Whispered Adhan",
        "subtitle": "A Mini Muslim Series Book",
        "author": "The Mini Muslim Series",
        "description": "A picture-book journey of the call to prayer, walking children through its meaning, beauty, and the daily rhythms of a Muslim life.",
        "cover_image": "https://images.unsplash.com/photo-1519682337058-a94d519337bc?auto=format&fit=crop&w=940&q=80",
        "amazon_paperback": "https://www.amazon.com/",
        "imprint": "kids",
        "category": "Children",
        "price": "$17.50",
        "pages": 36,
        "is_featured": False,
        "published_date": "2025",
        "status": "available",
    },
    {
        "title": "Whispers of the Heart",
        "subtitle": "A Companion to Tazkiyah",
        "author": "Minaret & Quill",
        "description": "A forthcoming companion volume on purifying the soul — drawing from classical works of tasawwuf and presenting them with clarity for the modern seeker.",
        "cover_image": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?auto=format&fit=crop&w=940&q=80",
        "imprint": "main",
        "category": "Spiritual Transformation",
        "is_featured": True,
        "status": "coming_soon",
        "expected_date": "Spring 2026",
    },
    {
        "title": "Tiny Hands, Tiny Du'as",
        "subtitle": "A Mini Muslim Series Book",
        "author": "The Mini Muslim Series",
        "description": "An upcoming picture book of everyday du'as — gentle words and tender illustrations that invite little hearts to remember Allah throughout their day.",
        "cover_image": "https://images.unsplash.com/photo-1522661067900-ab829854a57f?auto=format&fit=crop&w=940&q=80",
        "imprint": "kids",
        "category": "Children",
        "is_featured": True,
        "status": "coming_soon",
        "expected_date": "Summer 2026",
    },
]

PLACEHOLDER_ANNOUNCEMENTS = [
    {
        "title": "Now Open: Pre-orders for our Founding Collection",
        "body": "Our inaugural three titles are now available for pre-order on Amazon. Be among the first to hold a Minaret & Quill House book in your hands.",
        "cta_label": "Browse the Catalogue",
        "cta_link": "/books",
    },
    {
        "title": "Introducing The Mini Muslim Series",
        "body": "Our children's imprint is dedicated to nurturing fitrah, imagination, and foundational aqidah — one beautifully illustrated book at a time.",
        "cta_label": "Discover Kids Books",
        "cta_link": "/books?imprint=kids",
    },
    {
        "title": "Subscribe for Early Access",
        "body": "Join our newsletter for first looks at upcoming titles, behind-the-scenes notes from our editors, and reader-only previews.",
        "cta_label": "Subscribe",
        "cta_link": "#newsletter",
    },
]


async def seed_defaults(session: AsyncSession, admin_email: str, admin_password: str, hash_password, verify_password):
    """Ensure admin user exists; seed placeholder content once if tables are empty."""
    # Admin
    result = await session.execute(select(User).where(User.email == admin_email))
    user = result.scalar_one_or_none()
    if user is None:
        session.add(User(
            id=str(uuid.uuid4()),
            email=admin_email,
            password_hash=hash_password(admin_password),
            role="admin",
        ))
        await session.commit()
    elif not verify_password(admin_password, user.password_hash):
        user.password_hash = hash_password(admin_password)
        await session.commit()

    # Books — seed only if empty
    count = (await session.execute(select(Book))).scalars().all()
    if len(count) == 0:
        for b in PLACEHOLDER_BOOKS:
            session.add(Book(id=str(uuid.uuid4()), **b))
        await session.commit()

    # Announcements — seed only if empty
    count = (await session.execute(select(Announcement))).scalars().all()
    if len(count) == 0:
        for a in PLACEHOLDER_ANNOUNCEMENTS:
            session.add(Announcement(id=str(uuid.uuid4()), **a))
        await session.commit()
