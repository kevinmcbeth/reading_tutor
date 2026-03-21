#!/usr/bin/env python3
"""One-time migration script: reads existing SQLite data and inserts into PostgreSQL.

Creates a default family for existing children.

Usage:
    python scripts/migrate_sqlite_to_pg.py [--sqlite-path backend/data/reading_tutor.db]
"""
import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path

import asyncpg


async def migrate(sqlite_path: str, pg_url: str) -> None:
    db_path = Path(sqlite_path)
    if not db_path.exists():
        print(f"SQLite database not found at {db_path}")
        sys.exit(1)

    print(f"Connecting to SQLite: {db_path}")
    sqlite_conn = sqlite3.connect(str(db_path))
    sqlite_conn.row_factory = sqlite3.Row

    print(f"Connecting to PostgreSQL: {pg_url}")
    pg_conn = await asyncpg.connect(pg_url)

    try:
        # Create default family for existing data
        family_id = await pg_conn.fetchval(
            "INSERT INTO families (username, password_hash, display_name) "
            "VALUES ($1, $2, $3) "
            "ON CONFLICT (username) DO UPDATE SET username = $1 "
            "RETURNING id",
            "default",
            "$2b$12$placeholder_hash_change_me",
            "Default Family",
        )
        print(f"Created/found default family with id={family_id}")

        # Migrate children
        children = sqlite_conn.execute("SELECT * FROM children").fetchall()
        child_id_map: dict[int, int] = {}
        for c in children:
            new_id = await pg_conn.fetchval(
                "INSERT INTO children (family_id, name, avatar, pin, created_at) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                family_id,
                c["name"],
                c["avatar"],
                c["pin"],
                c["created_at"],
            )
            child_id_map[c["id"]] = new_id
        print(f"Migrated {len(children)} children")

        # Migrate stories
        stories = sqlite_conn.execute("SELECT * FROM stories").fetchall()
        story_id_map: dict[int, int] = {}
        for s in stories:
            new_id = await pg_conn.fetchval(
                "INSERT INTO stories (family_id, title, topic, difficulty, theme, style, status, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id",
                family_id,
                s["title"],
                s["topic"],
                s["difficulty"],
                s["theme"],
                s["style"],
                s["status"],
                s["created_at"],
            )
            story_id_map[s["id"]] = new_id
        print(f"Migrated {len(stories)} stories")

        # Migrate story_sentences
        sentences = sqlite_conn.execute("SELECT * FROM story_sentences").fetchall()
        sentence_id_map: dict[int, int] = {}
        for s in sentences:
            if s["story_id"] not in story_id_map:
                continue
            new_id = await pg_conn.fetchval(
                "INSERT INTO story_sentences (story_id, idx, text, image_prompt, negative_prompt, image_path, has_image) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
                story_id_map[s["story_id"]],
                s["idx"],
                s["text"],
                s["image_prompt"],
                s["negative_prompt"],
                s["image_path"],
                bool(s["has_image"]),
            )
            sentence_id_map[s["id"]] = new_id
        print(f"Migrated {len(sentences)} sentences")

        # Migrate story_words
        words = sqlite_conn.execute("SELECT * FROM story_words").fetchall()
        word_id_map: dict[int, int] = {}
        for w in words:
            if w["sentence_id"] not in sentence_id_map:
                continue
            new_id = await pg_conn.fetchval(
                "INSERT INTO story_words (sentence_id, idx, text, audio_path, has_audio, is_challenge_word) "
                "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
                sentence_id_map[w["sentence_id"]],
                w["idx"],
                w["text"],
                w["audio_path"],
                bool(w["has_audio"]),
                bool(w["is_challenge_word"]),
            )
            word_id_map[w["id"]] = new_id
        print(f"Migrated {len(words)} words")

        # Migrate sessions
        sessions = sqlite_conn.execute("SELECT * FROM sessions").fetchall()
        session_id_map: dict[int, int] = {}
        for s in sessions:
            child_new = child_id_map.get(s["child_id"])
            story_new = story_id_map.get(s["story_id"])
            if not child_new or not story_new:
                continue
            new_id = await pg_conn.fetchval(
                "INSERT INTO sessions (child_id, story_id, attempt_number, score, total_words, completed_at) "
                "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
                child_new,
                story_new,
                s["attempt_number"],
                s["score"],
                s["total_words"],
                s["completed_at"],
            )
            session_id_map[s["id"]] = new_id
        print(f"Migrated {len(sessions)} sessions")

        # Migrate session_words
        session_words = sqlite_conn.execute("SELECT * FROM session_words").fetchall()
        count = 0
        for sw in session_words:
            session_new = session_id_map.get(sw["session_id"])
            word_new = word_id_map.get(sw["word_id"])
            if not session_new or not word_new:
                continue
            await pg_conn.execute(
                "INSERT INTO session_words (session_id, word_id, attempts, correct) "
                "VALUES ($1, $2, $3, $4)",
                session_new,
                word_new,
                sw["attempts"],
                bool(sw["correct"]),
            )
            count += 1
        print(f"Migrated {count} session words")

        # Migrate generation_jobs
        jobs = sqlite_conn.execute("SELECT * FROM generation_jobs").fetchall()
        job_id_map: dict[int, int] = {}
        for j in jobs:
            story_new = story_id_map.get(j["story_id"])
            if not story_new:
                continue
            new_id = await pg_conn.fetchval(
                "INSERT INTO generation_jobs (story_id, status, progress_pct, created_at, completed_at) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                story_new,
                j["status"],
                j["progress_pct"],
                j["created_at"],
                j["completed_at"],
            )
            job_id_map[j["id"]] = new_id
        print(f"Migrated {len(jobs)} generation jobs")

        # Migrate generation_logs
        logs = sqlite_conn.execute("SELECT * FROM generation_logs").fetchall()
        count = 0
        for log in logs:
            job_new = job_id_map.get(log["job_id"])
            if not job_new:
                continue
            await pg_conn.execute(
                "INSERT INTO generation_logs (job_id, level, message, timestamp) "
                "VALUES ($1, $2, $3, $4)",
                job_new,
                log["level"],
                log["message"],
                log["timestamp"],
            )
            count += 1
        print(f"Migrated {count} generation logs")

        print("\nMigration complete!")
        print(f"Default family created with username='default' (id={family_id})")
        print("IMPORTANT: Update the default family's password_hash by registering via the app,")
        print("or run: UPDATE families SET password_hash = '<bcrypt_hash>' WHERE id = 1;")

    finally:
        await pg_conn.close()
        sqlite_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL")
    parser.add_argument(
        "--sqlite-path",
        default="backend/data/reading_tutor.db",
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--pg-url",
        default="postgresql://reading_tutor:password@localhost:5432/reading_tutor",
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()
    asyncio.run(migrate(args.sqlite_path, args.pg_url))


if __name__ == "__main__":
    main()
