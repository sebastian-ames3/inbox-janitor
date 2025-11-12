#!/usr/bin/env python3
"""Run migration 007 to clear polluted email_actions data."""
import asyncio
import sys

# Add parent directory to path for imports
sys.path.insert(0, '/app')

from sqlalchemy import text
from app.core.database import engine


async def run_migration():
    """Clear polluted classification data."""
    print("🗑️  Running migration 007: Clear polluted email_actions data")
    print("=" * 60)

    async with engine.begin() as conn:
        # Drop immutability trigger
        print("1. Dropping immutability trigger...")
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;
        """))
        print("   ✅ Trigger dropped")

        # Clear all data
        print("2. Truncating email_actions table...")
        await conn.execute(text("TRUNCATE email_actions;"))
        print("   ✅ Table truncated")

        # Recreate immutability trigger
        print("3. Recreating immutability trigger...")
        await conn.execute(text("""
            CREATE TRIGGER email_actions_immutable
            BEFORE UPDATE OR DELETE ON email_actions
            FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();
        """))
        print("   ✅ Trigger recreated")

        # Verify
        result = await conn.execute(text("SELECT COUNT(*) FROM email_actions;"))
        count = result.scalar()
        print(f"\n✅ Migration complete. Remaining rows: {count}")

    print("=" * 60)
    print("🎉 Database cleared and ready for re-classification")


if __name__ == "__main__":
    asyncio.run(run_migration())
