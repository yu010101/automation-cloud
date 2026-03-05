#!/usr/bin/env python3
"""Migrate local SQLite databases to Turso.

Usage:
    # Migrate hub DB
    python scripts/migrate-to-turso.py --hub

    # Migrate eddie DB
    python scripts/migrate-to-turso.py --eddie

    # Migrate both
    python scripts/migrate-to-turso.py --hub --eddie

Requires env vars:
    TURSO_HUB_URL, TURSO_HUB_TOKEN (for --hub)
    TURSO_EDDIE_URL, TURSO_EDDIE_TOKEN (for --eddie)
"""

import argparse
import os
import sqlite3
import sys

try:
    import libsql_experimental as libsql
except ImportError:
    print("Error: pip install libsql-experimental")
    sys.exit(1)


def migrate_db(local_path: str, turso_url: str, turso_token: str, db_name: str):
    """Copy all tables from local SQLite to Turso."""
    print(f"\n{'='*50}")
    print(f"Migrating: {local_path} -> {turso_url}")
    print(f"{'='*50}")

    # Connect to local DB
    local = sqlite3.connect(local_path)
    local.row_factory = sqlite3.Row

    # Connect to Turso
    remote = libsql.connect(db_name, sync_url=turso_url, auth_token=turso_token)
    remote.sync()

    # Get all tables
    tables = [row[0] for row in local.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]

    print(f"Tables found: {tables}")

    for table in tables:
        # Get CREATE TABLE statement
        schema = local.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]

        # Create table on Turso (IF NOT EXISTS)
        schema_safe = schema.replace(f"CREATE TABLE {table}", f"CREATE TABLE IF NOT EXISTS {table}")
        remote.execute(schema_safe)
        remote.commit()

        # Get row count
        local_count = local.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"\n  {table}: {local_count} rows")

        if local_count == 0:
            continue

        # Get column names
        cols = [desc[0] for desc in local.execute(f"SELECT * FROM {table} LIMIT 1").description]

        # Copy data in batches
        batch_size = 100
        offset = 0
        copied = 0

        while True:
            rows = local.execute(
                f"SELECT * FROM {table} LIMIT ? OFFSET ?", (batch_size, offset)
            ).fetchall()

            if not rows:
                break

            placeholders = ",".join(["?"] * len(cols))
            col_names = ",".join(cols)
            insert_sql = f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})"

            for row in rows:
                try:
                    remote.execute(insert_sql, tuple(row))
                    copied += 1
                except Exception as e:
                    print(f"    WARN: skip row in {table}: {e}")

            remote.commit()
            offset += batch_size

        remote.sync()
        remote_count = remote.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"    Copied: {copied} | Remote total: {remote_count}")

    # Copy indexes
    indexes = local.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
    ).fetchall()
    for idx in indexes:
        sql = idx[0]
        if sql:
            safe_sql = sql.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS")
            try:
                remote.execute(safe_sql)
            except Exception as e:
                print(f"  WARN: index: {e}")
    remote.commit()
    remote.sync()

    local.close()
    print(f"\nMigration complete for {db_name}!")


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to Turso")
    parser.add_argument("--hub", action="store_true", help="Migrate hub DB")
    parser.add_argument("--eddie", action="store_true", help="Migrate eddie DB")
    args = parser.parse_args()

    if not args.hub and not args.eddie:
        parser.print_help()
        sys.exit(1)

    if args.hub:
        hub_path = os.path.expanduser("~/ai-hub/data/hub.db")
        if not os.path.exists(hub_path):
            print(f"Hub DB not found: {hub_path}")
            sys.exit(1)
        migrate_db(
            hub_path,
            os.environ["TURSO_HUB_URL"],
            os.environ["TURSO_HUB_TOKEN"],
            "hub.db",
        )

    if args.eddie:
        eddie_path = os.path.expanduser("~/influencer-agent/data/influencer_agent.db")
        if not os.path.exists(eddie_path):
            print(f"Eddie DB not found: {eddie_path}")
            sys.exit(1)
        migrate_db(
            eddie_path,
            os.environ["TURSO_EDDIE_URL"],
            os.environ["TURSO_EDDIE_TOKEN"],
            "eddie.db",
        )


if __name__ == "__main__":
    main()
