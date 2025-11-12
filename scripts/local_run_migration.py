#!/usr/bin/env python3
"""
Run migration 007 locally - clears polluted email_actions data.

Usage:
    python3 scripts/local_run_migration.py "postgresql://user:pass@host:port/db"
"""
import sys
import asyncio
import asyncpg


async def run_migration(database_url: str):
    """Clear polluted classification data."""
    print("🗑️  Running migration 007: Clear polluted email_actions data")
    print("=" * 60)

    # Convert psycopg2-style URL to asyncpg format if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql://", 1)

    conn = await asyncpg.connect(database_url)

    try:
        # Drop immutability trigger
        print("1. Dropping immutability trigger...")
        await conn.execute("""
            DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;
        """)
        print("   ✅ Trigger dropped")

        # Clear all data
        print("2. Truncating email_actions table...")
        await conn.execute("TRUNCATE email_actions;")
        print("   ✅ Table truncated")

        # Recreate immutability trigger
        print("3. Recreating immutability trigger...")
        await conn.execute("""
            CREATE TRIGGER email_actions_immutable
            BEFORE UPDATE OR DELETE ON email_actions
            FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();
        """)
        print("   ✅ Trigger recreated")

        # Verify
        count = await conn.fetchval("SELECT COUNT(*) FROM email_actions;")
        print(f"\n✅ Migration complete. Remaining rows: {count}")

    finally:
        await conn.close()

    print("=" * 60)
    print("🎉 Database cleared and ready for re-classification")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/local_run_migration.py <database_url>")
        print("\nGet your public DATABASE_URL from Railway:")
        print("1. Go to railway.app → inbox-janitor project")
        print("2. Click Postgres service → Connect tab")
        print("3. Copy 'Postgres Connection URL' (starts with postgresql://)")
        print("\nNote: Use the PUBLIC url, not the .railway.internal one")
        sys.exit(1)

    database_url = sys.argv[1]
    asyncio.run(run_migration(database_url))
