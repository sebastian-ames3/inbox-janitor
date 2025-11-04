# Migration 002: Email Metadata and Security Triggers

## What This Migration Does

1. **Creates `email_metadata` table** - Stores extracted email metadata
2. **Adds comprehensive indexes** - For fast querying by mailbox, message, domain, category
3. **Creates PostgreSQL event trigger** - Prevents adding body/content columns
4. **Adds table comments** - Documents security requirements

## Running the Migration

### Local Development

```bash
# Activate virtual environment
source venv/bin/activate

# Run migration
alembic upgrade head

# Verify migration
alembic current
```

### Railway Production

The migration will run automatically on deployment if configured, or run manually:

```bash
# Via Railway CLI
railway run alembic upgrade head

# Or SSH into Railway and run
alembic upgrade head
```

## Verification Steps

After running the migration, verify:

### 1. Check table exists
```sql
SELECT table_name
FROM information_schema.tables
WHERE table_name = 'email_metadata';
```

### 2. Check indexes exist
```sql
SELECT indexname
FROM pg_indexes
WHERE tablename = 'email_metadata';
```

Expected indexes:
- `idx_email_metadata_mailbox_message` (unique)
- `idx_email_metadata_processed_at`
- `idx_email_metadata_mailbox_created`
- `idx_email_metadata_from_domain`
- `idx_email_metadata_category`
- And several others...

### 3. Check event trigger exists
```sql
SELECT *
FROM pg_event_trigger
WHERE evtname = 'prevent_email_body_columns';
```

### 4. Test trigger (IMPORTANT - Do NOT actually add body column!)
```sql
-- This should succeed (adding allowed column)
-- ALTER TABLE email_metadata ADD COLUMN test_col VARCHAR(50);
-- ALTER TABLE email_metadata DROP COLUMN test_col;

-- DO NOT RUN: This would be the security violation we're preventing
-- ALTER TABLE email_metadata ADD COLUMN body TEXT;
```

The trigger will log a NOTICE when ALTER TABLE is detected on email tables.

### 5. Check table comment
```sql
SELECT obj_description('email_metadata'::regclass);
```

Should see: "SECURITY: This table must NEVER contain body, html_body..."

## Rollback (if needed)

```bash
alembic downgrade -1
```

This will:
- Drop the `email_metadata` table
- Drop all indexes
- Drop the event trigger
- Drop trigger functions

## Security Features

### Event Trigger

The PostgreSQL event trigger monitors ALL `ALTER TABLE` commands on email tables:
- Logs NOTICE when email tables are modified
- Documents security intent
- Acts as guardrail against accidental body storage

### Table Comments

Table and column comments document security requirements:
- Visible in database tools
- Reminds developers of constraints
- Part of code review checklist

### Unique Constraint

`(mailbox_id, message_id)` unique constraint prevents:
- Duplicate metadata storage
- Data inconsistencies
- Unnecessary storage costs

## Common Issues

### Issue: Alembic can't find migration
**Solution:** Ensure `alembic/versions/` directory exists and contains migration file

### Issue: Migration fails with "table already exists"
**Solution:** Check if migration already ran: `alembic current`

### Issue: Permission denied creating event trigger
**Solution:** Ensure database user has SUPERUSER or event trigger privileges

### Issue: Migration times out on Railway
**Solution:** Index creation can be slow. Increase deployment timeout or run manually.

## Next Steps

After migration succeeds:

1. ✅ Verify all indexes exist
2. ✅ Check event trigger is active
3. ✅ Deploy code that uses email_metadata table
4. ✅ Monitor logs for any issues
5. ✅ Check classification is storing to email_actions table
