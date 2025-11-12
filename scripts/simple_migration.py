#!/usr/bin/env python3
"""
Run migration 007 using only standard library (psycopg2).

Usage:
    python3 scripts/simple_migration.py "postgresql://user:pass@host:port/db"
"""
import sys

try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 not installed")
    print("\nInstall it with: pip install psycopg2-binary")
    print("Or use: python3 -m pip install psycopg2-binary")
    sys.exit(1)


def run_migration(database_url: str):
    """Clear polluted classification data."""
    print("🗑️  Running migration 007: Clear polluted email_actions data")
    print("=" * 60)

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    try:
        # Drop immutability trigger
        print("1. Dropping immutability trigger...")
        cur.execute("""
            DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;
        """)
        conn.commit()
        print("   ✅ Trigger dropped")

        # Clear all data
        print("2. Truncating email_actions table...")
        cur.execute("TRUNCATE email_actions;")
        conn.commit()
        print("   ✅ Table truncated")

        # Recreate immutability trigger
        print("3. Recreating immutability trigger...")
        cur.execute("""
            CREATE TRIGGER email_actions_immutable
            BEFORE UPDATE OR DELETE ON email_actions
            FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();
        """)
        conn.commit()
        print("   ✅ Trigger recreated")

        # Verify
        cur.execute("SELECT COUNT(*) FROM email_actions;")
        count = cur.fetchone()[0]
        print(f"\n✅ Migration complete. Remaining rows: {count}")

    finally:
        cur.close()
        conn.close()

    print("=" * 60)
    print("🎉 Database cleared and ready for re-classification")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/simple_migration.py <database_url>")
        print("\nGet your PUBLIC DATABASE_URL from Railway:")
        print("1. Go to railway.app → inbox-janitor-production project")
        print("2. Click Postgres service (database icon)")
        print("3. Click 'Connect' tab")
        print("4. Look for 'Postgres Connection URL' with PUBLIC HOST")
        print("   (Should NOT contain .railway.internal)")
        print("\nExample format:")
        print("postgresql://postgres:password@roundhouse.proxy.rlwy.net:12345/railway")
        sys.exit(1)

    database_url = sys.argv[1]
    run_migration(database_url)
