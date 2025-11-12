#!/usr/bin/env python3
"""
Sample and classify emails from Gmail backlog with checkpoint system.

Fetches random sample of emails and classifies them in batches.
After each batch, shows distribution and asks whether to continue.
"""
import asyncio
import sys
import random
from typing import List, Dict
from sqlalchemy import select, func

# Add parent directory to path for imports
sys.path.insert(0, '/app')

from app.core.database import AsyncSessionLocal
from app.models.users import User
from app.models.mailboxes import Mailbox
from app.models.email_actions import EmailAction
from app.modules.gmail.service import get_gmail_service
from app.tasks.classify import classify_email_task


BATCH_SIZE = 250
TOTAL_SAMPLE = 1000


async def get_mailbox():
    """Get the first active mailbox."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Mailbox).where(Mailbox.is_active == True).limit(1)
        )
        mailbox = result.scalar_one_or_none()
        if not mailbox:
            print("❌ No active mailbox found")
            sys.exit(1)
        return mailbox


async def fetch_all_message_ids(mailbox: Mailbox) -> List[str]:
    """Fetch all message IDs from Gmail."""
    print("📧 Fetching all message IDs from Gmail...")

    gmail_service = await get_gmail_service(mailbox)
    message_ids = []
    page_token = None

    while True:
        try:
            results = gmail_service.users().messages().list(
                userId='me',
                maxResults=500,  # Gmail API max per page
                pageToken=page_token
            ).execute()

            messages = results.get('messages', [])
            message_ids.extend([msg['id'] for msg in messages])

            page_token = results.get('nextPageToken')
            if not page_token:
                break

            print(f"   Fetched {len(message_ids)} message IDs so far...")

        except Exception as e:
            print(f"❌ Error fetching messages: {e}")
            break

    print(f"✅ Total message IDs fetched: {len(message_ids)}")
    return message_ids


async def show_distribution():
    """Show current classification distribution."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                EmailAction.action,
                func.count(EmailAction.id).label('count')
            ).group_by(EmailAction.action)
        )
        rows = result.all()

        total = sum(row.count for row in rows)
        if total == 0:
            print("\n📊 No classifications yet")
            return

        print(f"\n📊 Distribution ({total} emails):")
        print("=" * 50)

        for row in sorted(rows, key=lambda r: r.count, reverse=True):
            pct = (row.count / total * 100)
            bar = "█" * int(pct / 2)  # Scale to 50 chars max
            print(f"  {row.action.upper():8} {row.count:4} ({pct:5.1f}%) {bar}")

        print("=" * 50)
        print(f"\n🎯 Target: KEEP ~15%, REVIEW ~5%, ARCHIVE ~30%, TRASH ~50%")


async def classify_batch(mailbox: Mailbox, message_ids: List[str], batch_num: int):
    """Classify a batch of emails."""
    print(f"\n🔄 Processing batch {batch_num} ({len(message_ids)} emails)...")

    for i, message_id in enumerate(message_ids, 1):
        try:
            # Call the classify task synchronously (we're already in async context)
            await classify_email_task(str(mailbox.id), message_id)

            if i % 50 == 0:
                print(f"   Processed {i}/{len(message_ids)}...")

        except Exception as e:
            print(f"   ⚠️  Error classifying {message_id}: {e}")
            continue

    print(f"✅ Batch {batch_num} complete")


def ask_continue() -> bool:
    """Ask user if they want to continue to next batch."""
    print("\n" + "=" * 50)
    response = input("\n❓ Continue to next batch? (y/n): ").strip().lower()
    return response == 'y'


async def main():
    """Main sampling and classification loop."""
    print("=" * 50)
    print("🔬 Email Classifier Sampling Tool")
    print("=" * 50)
    print(f"   Sample size: {TOTAL_SAMPLE} emails")
    print(f"   Batch size: {BATCH_SIZE} emails")
    print(f"   Checkpoints: Every {BATCH_SIZE} emails")
    print("=" * 50)

    # Get mailbox
    mailbox = await get_mailbox()
    print(f"\n✅ Using mailbox: {mailbox.email_address}")

    # Fetch all message IDs
    all_message_ids = await fetch_all_message_ids(mailbox)

    if len(all_message_ids) < TOTAL_SAMPLE:
        print(f"⚠️  Only {len(all_message_ids)} emails available, using all of them")
        sample_size = len(all_message_ids)
    else:
        sample_size = TOTAL_SAMPLE

    # Random sample
    sample_ids = random.sample(all_message_ids, sample_size)
    print(f"\n🎲 Randomly selected {len(sample_ids)} emails for classification")

    # Process in batches
    for batch_num in range(1, (sample_size // BATCH_SIZE) + 2):
        start_idx = (batch_num - 1) * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, sample_size)

        if start_idx >= sample_size:
            break

        batch_ids = sample_ids[start_idx:end_idx]

        # Classify batch
        await classify_batch(mailbox, batch_ids, batch_num)

        # Show distribution
        await show_distribution()

        # Ask to continue (unless this is the last batch)
        if end_idx < sample_size:
            if not ask_continue():
                print("\n🛑 Stopping early (user requested)")
                break
        else:
            print("\n✅ All batches complete!")

    # Final summary
    print("\n" + "=" * 50)
    print("📊 Final Distribution")
    print("=" * 50)
    await show_distribution()
    print("\n✅ Sampling complete")


if __name__ == "__main__":
    asyncio.run(main())
