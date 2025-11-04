# Git Workflow Skill

## Purpose
Enforce safe git commit patterns and Railway deployment verification for Inbox Janitor.

## Overview

**Critical Rule**: NEVER push code to production without verifying Railway deployment succeeds.

This skill teaches the complete workflow from writing code → committing → deploying → verifying.

## Git Workflow Rules

### CRITICAL RULES - NEVER VIOLATE:

1. **NEVER push directly to main branch**
   - ALWAYS create a feature branch for ALL changes
   - ALWAYS create a pull request (PR) to merge to main
   - NEVER use `git push origin main` directly
   - Exception: None (no exceptions allowed)

2. **ALWAYS wait for CI/CD checks and Railway build to complete** before merging PR
   - After creating PR, monitor GitHub Actions/checks
   - Wait for Railway deployment to succeed
   - Verify health check returns 200 OK
   - Only merge PR after all checks pass

3. **ALWAYS wait for Railway deployment to succeed** before considering work complete
   - After merging PR, monitor Railway deployment logs
   - Verify the build completes successfully
   - Test the deployed app on Railway domain
   - If deployment fails, create hotfix branch and new PR

4. **NEVER commit secrets to the repository**
   - GitHub push protection will block API keys
   - Use placeholder values in documentation files
   - Keep real secrets in `.env` (gitignored) and Railway Variables only

## Pre-Commit Checklist

Before `git commit`, verify:

- [ ] All security tests pass (`pytest tests/security/`)
- [ ] All safety tests pass (`pytest tests/safety/`)
- [ ] No secrets in code (`grep -r "sk-proj" app/` returns nothing)
- [ ] `.env` file is gitignored
- [ ] Code follows module patterns (see fastapi-module-builder.md)
- [ ] Security requirements met (see security-first.md)

## Commit Message Format

### Standard Commit Pattern

```bash
git commit -m "Subject line (50 chars max)

Optional body explaining WHAT changed and WHY.
Keep lines under 72 characters.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Subject Line Guidelines

**Good subject lines:**
- `Add OAuth token encryption to mailbox model`
- `Fix Railway deployment: correct Postmark package name`
- `Create Gmail webhook receiver module`
- `Add security tests for token encryption`

**Bad subject lines:**
- `fix bug` (too vague)
- `WIP` (work in progress should not be committed to main)
- `asdf` (meaningless)
- `Updated files` (too generic)

### Commit Types

Use these prefixes for clarity:

- `Add:` New feature or file
- `Fix:` Bug fix
- `Update:` Modify existing feature
- `Remove:` Delete feature or file
- `Refactor:` Code restructuring, no behavior change
- `Docs:` Documentation only
- `Test:` Add or update tests

### Examples

```bash
# Feature addition
git commit -m "Add Gmail watch + Pub/Sub webhook setup

Implements Gmail watch registration and Pub/Sub topic creation
for real-time email notifications.

Closes #2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Bug fix
git commit -m "Fix Railway dependencies: correct Postmark package name

Changed python-postmark package version from 1.0.1 to 0.7.0
to match PyPI availability.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Security update
git commit -m "Add token encryption tests

Implements test_token_encryption() and test_token_not_in_logs()
to prevent OAuth token leakage.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Git Commit Commands

### REQUIRED Workflow (Feature Branch → PR)

```bash
# 0. ALWAYS start with feature branch (NEVER work on main)
git checkout main
git pull origin main
git checkout -b feature/oauth-implementation

# 1. Stage changes
git add app/modules/auth/routes.py
git add tests/security/test_token_encryption.py

# Or stage all changes
git add .

# 2. Review changes
git diff --staged

# 3. Commit with message
git commit -m "Add OAuth endpoint with token encryption

Implements /auth/connect and /auth/google/callback endpoints.
Tokens are encrypted using Fernet before database storage.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 4. Push feature branch to GitHub (NOT main)
git push -u origin feature/oauth-implementation

# 5. Create pull request
gh pr create --title "Add OAuth implementation" --body "$(cat <<'EOF'
## Summary
- Implemented OAuth flow for Gmail
- Added token encryption with Fernet
- Created auth module routes

## Test plan
- [ ] Run security tests
- [ ] Test OAuth flow end-to-end
- [ ] Verify Railway deployment

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

# 6. WAIT for checks to pass
gh pr checks

# 7. WAIT for Railway preview deployment (if configured)
# Check deployment logs

# 8. User reviews and merges PR (or use gh pr merge after approval)
```

### Advanced Workflows

#### Amend Last Commit (Use Sparingly)

Only amend if:
1. Commit not yet pushed, OR
2. Fixing pre-commit hook changes

**Before amending, ALWAYS check authorship:**
```bash
# Check last commit author
git log -1 --format='%an %ae'

# Only amend if YOU are the author
git add forgotten_file.py
git commit --amend --no-edit

# Force push (only if not on main branch)
git push --force
```

#### Interactive Staging

```bash
# Review each change before staging
git add -p
```

#### Stash Changes

```bash
# Save changes temporarily
git stash

# List stashes
git stash list

# Apply stashed changes
git stash pop
```

## Deployment Verification Checklist

After `git push`, complete this checklist:

### Step 1: Code Pushed to GitHub
```bash
git push origin main
# Verify: Check GitHub for latest commit
```

### Step 2: GitHub Actions/Checks Passed (if configured)
```bash
# View status in GitHub
# All checks should show ✅ green
```

### Step 3: Railway Build Completed

Watch Railway build logs:
```bash
# Option 1: Railway dashboard
# Go to https://railway.app → Your Project → Deployments

# Option 2: CLI (if available)
railway logs --deployment latest
```

**Look for:**
- ✅ `Building...` → `Deployed` (success)
- ❌ `Failed` → Read error logs, fix, push again

### Step 4: Railway Deployment Successful

Check runtime logs:
```bash
railway logs --limit 50
```

**Look for:**
- ✅ "Starting Inbox Janitor..."
- ✅ "Environment: production"
- ✅ "Uvicorn running on 0.0.0.0:$PORT"
- ❌ "Field required" → Missing env var
- ❌ "Database connection failed" → Check DATABASE_URL

### Step 5: Health Check Returns 200 OK

```bash
curl https://inbox-janitor-production-03fc.up.railway.app/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "service": "Inbox Janitor",
  "environment": "production"
}
```

### Step 6: No Errors in Railway Logs

```bash
railway logs --limit 100 | grep -i error
# Should return no critical errors
```

**If deployment fails:**
- Read build logs for errors
- Read runtime logs for startup errors
- Fix the issue locally
- Commit and push again
- Repeat until deployment succeeds

## Branch Strategy

### Main Branch (production) - PROTECTED

**CRITICAL: NEVER push directly to main. ALWAYS use pull requests.**

- Protected branch (no force push, no direct commits)
- All changes via pull requests only
- Must pass all tests before PR merge
- Must pass Railway deployment before PR merge
- Code review by user (approve PR before merge)

### Feature Branch Workflow (REQUIRED FOR ALL CHANGES)

**Step 1: Create Feature Branch**
```bash
# ALWAYS start from latest main
git checkout main
git pull origin main

# Create feature branch (descriptive name)
git checkout -b feature/skills-system
# or
git checkout -b fix/railway-deployment
# or
git checkout -b test/security-tests
```

**Step 2: Make Changes and Commit**
```bash
# Work on feature
git add .
git commit -m "Add comprehensive skills system"

# Push feature branch to GitHub
git push -u origin feature/skills-system
```

**Step 3: Create Pull Request**
```bash
# Create PR using gh CLI
gh pr create --title "Add Claude Skills system" --body "..."

# Or create PR via GitHub web interface
```

**Step 4: Wait for Checks**
```bash
# Monitor PR status
gh pr view

# Wait for:
# - GitHub Actions (if configured)
# - Railway preview deployment (if configured)
# - All checks to pass
```

**Step 5: Merge PR (Only After Checks Pass)**
```bash
# User reviews and approves PR
# Then merge (squash and merge recommended)
gh pr merge --squash

# Delete feature branch after merge
git branch -d feature/skills-system
git push origin --delete feature/skills-system
```

### Branch Naming (Required Format)

**Pattern:** `<type>/<description>`

**Types:**
- `feature/` - New features (e.g., `feature/gmail-webhooks`)
- `fix/` - Bug fixes (e.g., `fix/railway-deployment`)
- `refactor/` - Code refactoring (e.g., `refactor/auth-module`)
- `test/` - Test additions (e.g., `test/security-tests`)
- `docs/` - Documentation (e.g., `docs/update-readme`)
- `hotfix/` - Urgent production fixes (e.g., `hotfix/token-leak`)

**Examples:**
- `feature/backlog-cleanup`
- `fix/oauth-token-refresh`
- `test/security-token-encryption`
- `docs/skills-system`

**NEVER name a branch `main` or `master`**

## Creating Pull Requests

**IMPORTANT: When the user asks you to create a pull request, follow the instructions in CLAUDE.md Git Workflow section (use gh pr create with HEREDOC for body formatting).**

### PR Creation Pattern

```bash
# 1. Ensure all commits are pushed
git push -u origin feature/my-feature

# 2. Check diff from main
git diff main...HEAD

# 3. Run through commits on branch
git log main..HEAD --oneline

# 4. Create PR with gh CLI
gh pr create --title "Add Gmail webhook receiver" --body "$(cat <<'EOF'
## Summary
- Created webhook receiver module for Gmail notifications
- Set up Pub/Sub topic and subscription
- Added rate limiting and retry logic

## Test plan
- [ ] Test OAuth flow end-to-end
- [ ] Verify webhook receives notifications
- [ ] Test rate limiting with 100+ emails
- [ ] Run security tests

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

# 5. Wait for CI/CD checks
# 6. Review and merge
```

## Handling Merge Conflicts

```bash
# Update main branch
git checkout main
git pull

# Merge main into feature branch
git checkout feature/my-feature
git merge main

# If conflicts:
# 1. Resolve conflicts in editor
# 2. Stage resolved files
git add conflicted_file.py

# 3. Commit merge
git commit -m "Merge main into feature/my-feature"

# 4. Push
git push
```

## Git Mistakes & Recovery

### Undo Last Commit (Not Pushed)

```bash
# Keep changes, undo commit
git reset --soft HEAD~1

# Discard changes, undo commit
git reset --hard HEAD~1
```

### Undo Last Commit (Already Pushed)

```bash
# Create reverting commit
git revert HEAD
git push
```

### Recover Deleted File

```bash
# Find commit that deleted file
git log --all --full-history -- path/to/file

# Restore file from commit before deletion
git checkout <commit>^ -- path/to/file
```

### Accidentally Committed Secret

```bash
# 1. Remove secret from code
git rm --cached .env

# 2. Add to .gitignore
echo ".env" >> .gitignore

# 3. Commit removal
git commit -m "Remove accidentally committed .env file"

# 4. Force push (DANGER - only if absolutely necessary)
git push --force

# 5. Rotate the compromised secret immediately
```

## Git Secrets Prevention

### Pre-Commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

# Check for secrets
if grep -r "sk-proj-" app/ 2>/dev/null; then
    echo "ERROR: Found OpenAI API key in code"
    exit 1
fi

if grep -r "GOOGLE_CLIENT_SECRET\s*=" app/ 2>/dev/null; then
    echo "ERROR: Found hardcoded Google secret"
    exit 1
fi

# Run security tests
pytest tests/security/ || exit 1
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Railway Deployment Failures

### Debugging Failed Deployments

If Railway deployment fails after push:

```bash
# 1. Check build logs
railway logs --deployment latest

# 2. Look for error patterns
# - "ModuleNotFoundError" → Missing dependency
# - "SyntaxError" → Python syntax error
# - "Field required" → Missing env var

# 3. Fix locally
# Edit requirements.txt or fix syntax

# 4. Test locally
uvicorn app.main:app --reload

# 5. Commit and push fix
git add .
git commit -m "Fix Railway deployment: add missing dependency"
git push

# 6. Monitor new deployment
railway logs --follow
```

## Quick Reference

### Common Commands

```bash
# Status
git status

# View commits
git log --oneline -10

# View changes
git diff

# Stage all changes
git add .

# Commit
git commit -m "message"

# Push
git push

# Pull latest
git pull

# View remotes
git remote -v
```

### Emergency Commands

```bash
# Abort merge
git merge --abort

# Abort rebase
git rebase --abort

# Discard all local changes
git checkout .

# Undo last commit (keep changes)
git reset --soft HEAD~1
```

## Related Skills

- **railway-deployment.md** - Deployment verification after push
- **testing-requirements.md** - Tests to run before commit
- **security-first.md** - Secrets management patterns
