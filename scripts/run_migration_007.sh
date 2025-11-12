#!/bin/bash
# Run migration 007 to clear polluted email_actions data

psql $DATABASE_URL <<EOF
-- Drop immutability trigger
DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;

-- Clear all data
TRUNCATE email_actions;

-- Recreate immutability trigger
CREATE TRIGGER email_actions_immutable
BEFORE UPDATE OR DELETE ON email_actions
FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();

-- Verify
SELECT COUNT(*) as remaining_rows FROM email_actions;
EOF
