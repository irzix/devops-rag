"""
Migration: Add feedback_rating and feedback_comment columns to chatmessage table.

Run once on the production server:
    python scripts/migrate_add_feedback_columns.py

Safe to re-run — skips columns that already exist.
"""
import sqlite3
import os
import sys

DB_PATH = os.environ.get("DB_PATH", "data/devops_rag.db")


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run_migration(db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    migrations = [
        ("feedback_rating",  "ALTER TABLE chatmessage ADD COLUMN feedback_rating TEXT DEFAULT NULL"),
        ("feedback_comment", "ALTER TABLE chatmessage ADD COLUMN feedback_comment TEXT DEFAULT NULL"),
    ]

    for col_name, sql in migrations:
        if column_exists(cur, "chatmessage", col_name):
            print(f"[SKIP]  Column '{col_name}' already exists.")
        else:
            cur.execute(sql)
            print(f"[OK]    Column '{col_name}' added successfully.")

    conn.commit()
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    print(f"Running migration on: {target}\n")
    run_migration(target)
