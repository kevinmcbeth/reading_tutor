import asyncpg

from config import settings

_pool: asyncpg.Pool | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS families (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS children (
    id SERIAL PRIMARY KEY,
    family_id INTEGER REFERENCES families(id) NOT NULL,
    name TEXT NOT NULL,
    avatar TEXT,
    pin TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stories (
    id SERIAL PRIMARY KEY,
    family_id INTEGER REFERENCES families(id),
    uuid TEXT,
    title TEXT,
    topic TEXT,
    difficulty TEXT,
    theme TEXT,
    style TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS story_sentences (
    id SERIAL PRIMARY KEY,
    story_id INTEGER REFERENCES stories(id),
    idx INTEGER,
    text TEXT,
    image_prompt TEXT,
    negative_prompt TEXT,
    image_path TEXT,
    has_image BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS story_words (
    id SERIAL PRIMARY KEY,
    sentence_id INTEGER REFERENCES story_sentences(id),
    idx INTEGER,
    text TEXT,
    audio_path TEXT,
    has_audio BOOLEAN DEFAULT FALSE,
    is_challenge_word BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id),
    story_id INTEGER REFERENCES stories(id),
    attempt_number INTEGER DEFAULT 1,
    score INTEGER DEFAULT 0,
    total_words INTEGER DEFAULT 0,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_words (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    word_id INTEGER REFERENCES story_words(id),
    attempts INTEGER DEFAULT 0,
    correct BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id SERIAL PRIMARY KEY,
    story_id INTEGER REFERENCES stories(id),
    status TEXT DEFAULT 'pending',
    progress_pct REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generation_logs (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES generation_jobs(id),
    level TEXT,
    message TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);
"""


async def init_db() -> None:
    """Initialize the database connection pool and create tables."""
    global _pool
    _pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=20)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)


async def close_db() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the database connection pool."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool
