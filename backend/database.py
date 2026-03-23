import json
import logging

import asyncpg

from config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS families (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    words_per_coin INTEGER NOT NULL DEFAULT 10,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ensure words_per_coin column exists on families (may be missing on older DBs)
DO $$ BEGIN
    ALTER TABLE families ADD COLUMN words_per_coin INTEGER NOT NULL DEFAULT 10;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS children (
    id SERIAL PRIMARY KEY,
    family_id INTEGER REFERENCES families(id) NOT NULL,
    name TEXT NOT NULL,
    avatar TEXT,
    pin_hash TEXT,
    fp_level TEXT,
    fp_level_set_by TEXT DEFAULT 'auto',
    words_per_coin INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ensure words_per_coin column exists on children (may be missing on older DBs)
DO $$ BEGIN
    ALTER TABLE children ADD COLUMN words_per_coin INTEGER;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS stories (
    id SERIAL PRIMARY KEY,
    family_id INTEGER REFERENCES families(id),
    uuid TEXT,
    title TEXT,
    topic TEXT,
    difficulty TEXT,
    theme TEXT,
    style TEXT,
    fp_level TEXT,
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

CREATE TABLE IF NOT EXISTS fp_levels (
    id SERIAL PRIMARY KEY,
    level TEXT UNIQUE NOT NULL,
    sort_order INTEGER NOT NULL,
    grade_range TEXT,
    min_sentences INTEGER NOT NULL,
    max_sentences INTEGER NOT NULL,
    generate_images BOOLEAN DEFAULT TRUE,
    image_support TEXT,
    vocabulary_constraints JSONB,
    sentence_patterns JSONB,
    description TEXT
);

CREATE TABLE IF NOT EXISTS fp_progress (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL,
    fp_level TEXT NOT NULL,
    story_id INTEGER REFERENCES stories(id) NOT NULL,
    session_id INTEGER REFERENCES sessions(id) NOT NULL,
    accuracy REAL NOT NULL,
    completed_at TIMESTAMP DEFAULT NOW()
);

-- Foreign key indexes for JOIN/WHERE performance
CREATE INDEX IF NOT EXISTS idx_children_family_id ON children(family_id);
CREATE INDEX IF NOT EXISTS idx_stories_family_id_status ON stories(family_id, status);
CREATE INDEX IF NOT EXISTS idx_story_sentences_story_id ON story_sentences(story_id);
CREATE INDEX IF NOT EXISTS idx_story_words_sentence_id ON story_words(sentence_id);
CREATE INDEX IF NOT EXISTS idx_sessions_child_id ON sessions(child_id);
CREATE INDEX IF NOT EXISTS idx_sessions_story_id ON sessions(story_id);
CREATE INDEX IF NOT EXISTS idx_session_words_session_id ON session_words(session_id);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_story_id ON generation_jobs(story_id);
CREATE INDEX IF NOT EXISTS idx_generation_logs_job_id ON generation_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_fp_progress_child_level ON fp_progress(child_id, fp_level);
CREATE INDEX IF NOT EXISTS idx_stories_fp_level ON stories(fp_level);

CREATE TABLE IF NOT EXISTS reward_items (
    id SERIAL PRIMARY KEY,
    family_id INTEGER REFERENCES families(id) NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    emoji TEXT DEFAULT '🎁',
    cost INTEGER NOT NULL CHECK (cost > 0),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS redemptions (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL,
    item_id INTEGER REFERENCES reward_items(id) NOT NULL,
    cost INTEGER NOT NULL,
    redeemed_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coin_conversions (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL,
    words_spent INTEGER NOT NULL,
    coins_earned INTEGER NOT NULL,
    converted_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reward_items_family ON reward_items(family_id);
CREATE INDEX IF NOT EXISTS idx_redemptions_child ON redemptions(child_id);
CREATE INDEX IF NOT EXISTS idx_coin_conversions_child ON coin_conversions(child_id);

-- Math progress: per-child, per-subject grade tracking
CREATE TABLE IF NOT EXISTS math_progress (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL,
    subject TEXT NOT NULL,
    grade_level INTEGER NOT NULL DEFAULT 0,
    problems_attempted INTEGER NOT NULL DEFAULT 0,
    problems_correct INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    best_streak INTEGER NOT NULL DEFAULT 0,
    set_by TEXT NOT NULL DEFAULT 'auto',
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(child_id, subject)
);

-- Math sessions
CREATE TABLE IF NOT EXISTS math_sessions (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL,
    subject TEXT NOT NULL,
    grade_level INTEGER NOT NULL,
    problems_attempted INTEGER NOT NULL DEFAULT 0,
    problems_correct INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Individual math problem results
CREATE TABLE IF NOT EXISTS math_problems (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES math_sessions(id) NOT NULL,
    problem_type TEXT NOT NULL,
    problem_data JSONB NOT NULL,
    correct_answer TEXT NOT NULL,
    child_answer TEXT,
    correct BOOLEAN NOT NULL DEFAULT FALSE,
    attempts INTEGER NOT NULL DEFAULT 1,
    answered_at TIMESTAMP DEFAULT NOW()
);

-- Math-specific coin conversions
CREATE TABLE IF NOT EXISTS math_coin_conversions (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL,
    problems_spent INTEGER NOT NULL,
    coins_earned INTEGER NOT NULL,
    converted_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_math_progress_child ON math_progress(child_id);
CREATE INDEX IF NOT EXISTS idx_math_sessions_child ON math_sessions(child_id);
CREATE INDEX IF NOT EXISTS idx_math_problems_session ON math_problems(session_id);
CREATE INDEX IF NOT EXISTS idx_math_coin_conversions_child ON math_coin_conversions(child_id);

-- Migration: add math_problems_per_coin to families/children
DO $$ BEGIN
    ALTER TABLE families ADD COLUMN math_problems_per_coin INTEGER NOT NULL DEFAULT 20;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE children ADD COLUMN math_problems_per_coin INTEGER;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Analytics & scaling indexes
CREATE INDEX IF NOT EXISTS idx_sessions_child_completed ON sessions(child_id, completed_at) WHERE completed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_session_words_correct ON session_words(word_id, correct);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_created ON generation_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stories_created ON stories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fp_progress_accuracy ON fp_progress(child_id, fp_level, accuracy);
"""


FP_LEVEL_DATA = [
    # (level, sort_order, grade_range, min_sent, max_sent, gen_images, image_support, vocab_constraints, description)
    ("A", 1, "K", 1, 2, True, "heavy", {"type": "sight_words_only", "words": ["I","a","the","see","is","am","my","to","go","we","can","like","it","in","up","at","on"]}, "Emergent early reader — pattern text, 1-2 sentences, heavy picture support"),
    ("B", 2, "K", 1, 2, True, "heavy", {"type": "sight_words_only", "words": ["I","a","the","see","is","am","my","to","go","we","can","like","it","in","up","at","on"]}, "Emergent early reader — pattern text, 1-2 sentences, heavy picture support"),
    ("C", 3, "K-1", 2, 3, True, "strong", {"type": "cvc_plus_sight", "max_syllables": 1}, "Early reader — CVC words + sight words, simple plots"),
    ("D", 4, "1", 2, 3, True, "strong", {"type": "cvc_plus_sight", "max_syllables": 1}, "Early reader — CVC words + sight words, simple plots"),
    ("E", 5, "1", 3, 4, True, "moderate", {"type": "expanding", "max_syllables": 2, "allow_contractions": True}, "Early fluent — expanding vocabulary, simple dialogue"),
    ("F", 6, "1", 3, 4, True, "moderate", {"type": "expanding", "max_syllables": 2, "allow_contractions": True}, "Early fluent — expanding vocabulary, simple dialogue"),
    ("G", 7, "1-2", 4, 5, True, "light", {"type": "expanding", "max_syllables": 2, "allow_contractions": True}, "Transitional — longer sentences, light picture support"),
    ("H", 8, "1-2", 4, 5, True, "light", {"type": "expanding", "max_syllables": 2, "allow_contractions": True}, "Transitional — longer sentences, light picture support"),
    ("I", 9, "2", 5, 7, True, "minimal", {"type": "varied", "allow_compound": True, "allow_literary": True}, "Fluent reader — varied vocabulary, compound words"),
    ("J", 10, "2", 5, 7, True, "minimal", {"type": "varied", "allow_compound": True, "allow_literary": True}, "Fluent reader — varied vocabulary, compound words"),
    ("K", 11, "2-3", 6, 8, True, "sparse", {"type": "varied", "allow_compound": True, "allow_literary": True}, "Fluent reader — literary language, sparse images"),
    ("L", 12, "3", 6, 8, True, "sparse", {"type": "varied", "allow_compound": True, "allow_literary": True}, "Fluent reader — literary language, sparse images"),
    ("M", 13, "3", 8, 10, True, "rare", {"type": "varied", "allow_compound": True, "allow_literary": True}, "Independent reader — rare image support"),
    ("N", 14, "3-4", 8, 10, True, "rare", {"type": "varied", "allow_compound": True, "allow_literary": True}, "Independent reader — rare image support"),
    ("O", 15, "4", 10, 12, True, "rare", {"type": "grade_appropriate"}, "Advanced reader — grade-appropriate vocabulary"),
    ("P", 16, "4", 10, 12, True, "rare", {"type": "grade_appropriate"}, "Advanced reader"),
    ("Q", 17, "4-5", 12, 15, True, "rare", {"type": "grade_appropriate"}, "Advanced reader — longer texts"),
    ("R", 18, "5", 12, 15, True, "rare", {"type": "grade_appropriate"}, "Advanced reader — longer texts"),
    ("S", 19, "5", 15, 18, True, "rare", {"type": "grade_appropriate"}, "Proficient reader"),
    ("T", 20, "5-6", 15, 18, True, "rare", {"type": "grade_appropriate"}, "Proficient reader"),
    ("U", 21, "6", 18, 22, True, "rare", {"type": "grade_appropriate"}, "Proficient reader — sophisticated content"),
    ("V", 22, "6-7", 18, 22, True, "rare", {"type": "grade_appropriate"}, "Proficient reader — sophisticated content"),
    ("W", 23, "7", 20, 25, True, "rare", {"type": "grade_appropriate"}, "Expert reader"),
    ("X", 24, "7-8", 20, 25, True, "rare", {"type": "grade_appropriate"}, "Expert reader"),
    ("Y", 25, "8", 25, 30, True, "rare", {"type": "grade_appropriate"}, "Expert reader — complex themes"),
    ("Z", 26, "8+", 25, 30, True, "rare", {"type": "grade_appropriate"}, "Expert reader — complex themes"),
    ("Z1", 27, "9+", 30, 40, True, "rare", {"type": "grade_appropriate"}, "Advanced expert"),
    ("Z2", 28, "10+", 30, 40, True, "rare", {"type": "grade_appropriate"}, "Advanced expert"),
]


async def seed_fp_levels(conn) -> None:
    """Insert F&P level definitions if not already present."""
    existing = await conn.fetchval("SELECT COUNT(*) FROM fp_levels")
    if existing > 0:
        return

    for level, sort_order, grade_range, min_s, max_s, gen_images, img_support, vocab, desc in FP_LEVEL_DATA:
        await conn.execute(
            """INSERT INTO fp_levels (level, sort_order, grade_range, min_sentences, max_sentences,
               generate_images, image_support, vocabulary_constraints, description)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (level) DO NOTHING""",
            level, sort_order, grade_range, min_s, max_s, gen_images, img_support,
            json.dumps(vocab), desc,
        )
    logger.info("Seeded %d F&P level definitions", len(FP_LEVEL_DATA))


async def init_db() -> None:
    """Initialize the database connection pool and create tables."""
    global _pool
    _pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=settings.DB_POOL_MIN,
        max_size=settings.DB_POOL_MAX,
    )
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)
        await seed_fp_levels(conn)


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
