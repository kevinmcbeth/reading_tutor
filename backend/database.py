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

-- ========== Stock Market ==========

CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    symbol TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    emoji TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    base_price REAL NOT NULL DEFAULT 100.0,
    current_price REAL NOT NULL DEFAULT 100.0,
    volatility REAL NOT NULL DEFAULT 0.15,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stock_price_history (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) NOT NULL,
    price REAL NOT NULL,
    change_pct REAL NOT NULL DEFAULT 0,
    market_day DATE NOT NULL,
    UNIQUE(stock_id, market_day)
);

CREATE TABLE IF NOT EXISTS stock_stories (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) NOT NULL,
    fp_level TEXT NOT NULL,
    direction TEXT NOT NULL,
    headline TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS child_stock_balances (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL UNIQUE,
    coins REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS child_stock_holdings (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL,
    stock_id INTEGER REFERENCES stocks(id) NOT NULL,
    shares INTEGER NOT NULL DEFAULT 0,
    UNIQUE(child_id, stock_id)
);

CREATE TABLE IF NOT EXISTS child_stock_transactions (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES children(id) NOT NULL,
    stock_id INTEGER REFERENCES stocks(id) NOT NULL,
    action TEXT NOT NULL,
    shares INTEGER NOT NULL,
    price_per_share REAL NOT NULL,
    total REAL NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_price_history_stock_day ON stock_price_history(stock_id, market_day DESC);
CREATE INDEX IF NOT EXISTS idx_stock_stories_stock_level_dir ON stock_stories(stock_id, fp_level, direction);
CREATE INDEX IF NOT EXISTS idx_child_stock_holdings_child ON child_stock_holdings(child_id);
CREATE INDEX IF NOT EXISTS idx_child_stock_transactions_child ON child_stock_transactions(child_id, created_at DESC);

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


STOCK_DATA = [
    ("UNIC", "Unicorn Glitter Co.", "🦄", "magical", "Makes sparkly glitter from unicorn manes", 120.0, 0.20),
    ("BNNA", "Banana Pants Inc.", "🍌", "fashion", "Sells pants shaped like bananas", 45.0, 0.25),
    ("DINO", "Dino Egg Farms", "🦕", "food", "Grows dinosaur eggs for breakfast", 200.0, 0.18),
    ("SLME", "Super Slime Labs", "🧪", "toys", "Invents new kinds of slime every week", 80.0, 0.22),
    ("ROBO", "Robot Puppy Corp.", "🤖", "pets", "Builds robot puppies that fetch real sticks", 150.0, 0.15),
    ("PIZZ", "Pizza Planet Delivery", "🍕", "food", "Delivers pizza by rocket ship", 95.0, 0.12),
    ("RAIN", "Rainbow Bridge Builders", "🌈", "construction", "Builds real rainbow bridges between cities", 175.0, 0.17),
    ("SOCK", "Lost Sock Detective Agency", "🧦", "services", "Finds socks that went missing in the dryer", 30.0, 0.30),
    ("PILW", "Pillow Fort Architects", "🏰", "construction", "Designs epic pillow forts for kids", 65.0, 0.20),
    ("BBLE", "Bubble Gum Space Program", "🫧", "space", "Blows bubbles big enough to fly to the moon", 110.0, 0.25),
    ("MNST", "Monster Truck Daycare", "🚛", "transport", "Monster trucks that drive kids to school", 88.0, 0.19),
    ("JELL", "Jelly Bean Weather Service", "🫘", "weather", "Predicts weather by tasting jelly beans", 55.0, 0.23),
    ("DRAG", "Dragon Ride Airlines", "🐉", "transport", "Fly anywhere on a friendly dragon", 250.0, 0.16),
    ("CAKE", "Volcano Cake Bakery", "🌋", "food", "Bakes cakes that actually erupt with frosting", 70.0, 0.21),
    ("FART", "Fart Jar Collections", "💨", "collectibles", "Bottles rare and exotic farts from around the world", 15.0, 0.35),
    ("YETI", "Yeti Ice Cream Trucks", "🧊", "food", "Yetis that deliver ice cream in blizzards", 130.0, 0.14),
    ("WAND", "Magic Wand Repairs", "🪄", "services", "Fixes broken magic wands same day", 90.0, 0.18),
    ("CLDS", "Cloud Furniture Store", "☁️", "furniture", "Sells chairs and beds made of real clouds", 105.0, 0.16),
    ("POOP", "Golden Poop Trophy Co.", "💩", "awards", "Makes trophies shaped like golden poops", 25.0, 0.32),
    ("NINJA", "Ninja Cat Academy", "🐱", "education", "Trains cats to be sneaky ninjas", 140.0, 0.20),
]


async def seed_stocks(conn) -> None:
    """Insert stock definitions if not already present."""
    existing = await conn.fetchval("SELECT COUNT(*) FROM stocks")
    if existing > 0:
        return
    for symbol, name, emoji, category, desc, base_price, volatility in STOCK_DATA:
        await conn.execute(
            """INSERT INTO stocks (symbol, name, emoji, category, description, base_price, current_price, volatility)
               VALUES ($1, $2, $3, $4, $5, $6, $6, $7)
               ON CONFLICT (symbol) DO NOTHING""",
            symbol, name, emoji, category, desc, base_price, volatility,
        )
    logger.info("Seeded %d stocks", len(STOCK_DATA))


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
        await seed_stocks(conn)
        # Seed stock stories after stocks exist
        from services.stock_stories import seed_stock_stories
        stock_rows = await conn.fetch("SELECT id, symbol, name, emoji FROM stocks ORDER BY id")
        if stock_rows:
            stocks = [(r["id"], r["symbol"], r["name"], r["emoji"]) for r in stock_rows]
            count = await seed_stock_stories(conn, stocks)
            logger.info("Stock stories: %d in database", count)


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
