# AI Dev Workflow Skill

## Purpose
Structured approach to building complex features using PRD → Tasks → Execute workflow for maximum control and reviewability.

## Overview

For complex features (>50 lines of code, multiple files, Week 1-6 roadmap items), use a structured 3-step workflow instead of monolithic prompts.

**Benefits:**
- Reviewable progress (catch issues early)
- Clear task breakdown
- Step-by-step verification
- Prevents scope creep
- Better code quality

**When to use:**
- Building features from roadmap
- Complex multi-step implementations
- Features requiring multiple modules
- Anything with security implications

**When NOT to use:**
- Bug fixes
- Single-line changes
- Documentation updates
- Simple refactoring

## Workflow Steps

### Step 1: Create PRD (Product Requirements Document)

**Purpose**: Define WHAT you're building and WHY before writing code.

**Command:**
```
I want to build [feature name].
Use @ai-dev-tasks/create-prd.md to create a PRD.

[Describe your feature in detail:
 - What problem does it solve?
 - Who will use it?
 - What functionality is needed?
 - Any constraints or requirements?]

Reference @CLAUDE.md for architecture context.
```

**Example:**
```
I want to build the backlog cleanup feature.
Use @ai-dev-tasks/create-prd.md to create a PRD.

From CLAUDE.md roadmap (Week 3):
- Scan user's old emails (>6 months old)
- Show counts by Gmail category (promotions, social, etc)
- Give user a magic link to approve batch cleanup
- Rate limit to 10 emails/min to avoid Gmail quota
- Send progress updates during long cleanup operations

This is for mom/sister who have 5K-8K email backlogs.
Security critical: must respect exception keywords (job, medical, etc.)

Reference @CLAUDE.md for architecture context.
```

**What happens:**
1. Claude asks clarifying questions (answer with numbered lists)
2. Claude generates detailed PRD
3. PRD is saved to `/tasks/0001-prd-feature-name.md`

### Step 2: Generate Tasks from PRD

**Purpose**: Break down the PRD into actionable sub-tasks.

**Command:**
```
Take @tasks/0001-prd-feature-name.md and create tasks using @ai-dev-tasks/generate-tasks.md
```

**What happens:**
1. Claude analyzes PRD
2. Claude reviews existing codebase
3. Claude generates 5-7 high-level parent tasks
4. You say "Go"
5. Claude breaks down each parent task into sub-tasks
6. Claude identifies files to create/modify
7. Task list saved to `/tasks/tasks-0001-prd-feature-name.md`

**Example output:**
```markdown
## Tasks

- [ ] 1.0 Create backlog analysis module
  - [ ] 1.1 Add backlog scanning function
  - [ ] 1.2 Implement category counting logic
  - [ ] 1.3 Add date filtering (>6 months)
  - [ ] 1.4 Create backlog analysis response model
- [ ] 2.0 Implement rate limiting
  - [ ] 2.1 Add Redis-based rate limiter
  - [ ] 2.2 Configure 10 emails/min limit
  - [ ] 2.3 Add retry logic with exponential backoff
- [ ] 3.0 Create magic link system
  ...
```

### Step 3: Execute Tasks One-by-One

**Purpose**: Implement each sub-task with review checkpoints.

**Command:**
```
Start on task 1.1 from the generated task list and work through it step-by-step.
After I review each sub-task, I'll say "yes" to continue or provide feedback.
```

**What happens:**
1. Claude does ONE sub-task (e.g., 1.1)
2. Claude shows you the changes
3. You review and say "yes" or give feedback
4. Claude moves to next sub-task (1.2)
5. Repeat until parent task (1.0) complete
6. Claude runs tests after each parent task
7. Claude commits changes
8. Repeat for all tasks

**Your job:**
- Review each sub-task completion
- Say "yes" if it looks good
- Give feedback if something's wrong
- Don't just rubber-stamp - actually review!

## Integration with Existing Skills

When executing tasks, Claude automatically applies these skills:

- **security-first.md** - When handling OAuth/tokens
- **fastapi-module-builder.md** - When creating modules
- **email-classification.md** - When implementing classification
- **testing-requirements.md** - When writing tests
- **railway-deployment.md** - When deploying
- **git-workflow.md** - When committing

## Example: Complete Workflow

### Scenario: Building Gmail Webhook Receiver

**Step 1: Create PRD**
```
I want to build the Gmail webhook receiver.
Use @ai-dev-tasks/create-prd.md to create a PRD.

From CLAUDE.md roadmap (Week 1-2):
- Receive Gmail push notifications via Pub/Sub
- Verify webhook authenticity
- Extract message IDs from notifications
- Queue emails for classification
- Handle rate limiting and retries

This is critical for real-time email processing.
Must integrate with existing auth module.

Reference @CLAUDE.md for architecture context.
```

**Claude asks clarifying questions:**
```
1. Should the webhook validate Google's JWT token?
   a) Yes, use Google's public keys
   b) No, trust the source IP
   c) Use both methods

2. How should we queue emails for processing?
   a) Celery background tasks
   b) Direct processing (blocking)
   c) Redis queue

3. What should happen if classification fails?
   ...
```

**You answer:**
```
1. a
2. a
3. Log error and retry with exponential backoff
```

**Claude generates PRD** → Saved to `/tasks/0002-prd-gmail-webhook-receiver.md`

**Step 2: Generate Tasks**
```
Take @tasks/0002-prd-gmail-webhook-receiver.md and create tasks using @ai-dev-tasks/generate-tasks.md
```

**Claude shows parent tasks:**
```
1.0 Create webhook endpoint module
2.0 Implement JWT verification
3.0 Set up Celery task queue
4.0 Add rate limiting and retry logic
5.0 Write integration tests
6.0 Deploy to Railway

Ready to generate sub-tasks? Respond with 'Go' to proceed.
```

**You say:** `Go`

**Claude generates detailed sub-tasks** → Saved to `/tasks/tasks-0002-prd-gmail-webhook-receiver.md`

**Step 3: Execute**
```
Start on task 1.1 from the generated task list.
```

**Claude:**
```
Task 1.1: Create webhook module structure

I'll create:
- app/modules/ingest/__init__.py
- app/modules/ingest/routes.py
- app/modules/ingest/service.py

[Shows code for routes.py with POST /webhooks/gmail endpoint]

Review this implementation. Say "yes" to continue or provide feedback.
```

**You:** `yes`

**Claude:**
```
Task 1.2: Add webhook request validation

[Shows code for validating Pub/Sub message format]

Review this implementation. Say "yes" to continue or provide feedback.
```

**You:** `yes`

... continues until all tasks complete

## Workflow Advantages

### Without Structured Workflow

```
You: "Build Gmail webhook receiver"
Claude: [Generates 500 lines across 10 files]
You: "Wait, this doesn't handle rate limiting..."
Claude: [Rewrites large portions]
You: "Now the tests are broken..."
Claude: [Fixes tests, breaks something else]
Time: 2 hours, lots of back-and-forth
```

### With Structured Workflow

```
You: [Creates PRD] → [Generates tasks] → [Executes task 1.1]
Claude: "Added webhook endpoint (20 lines)"
You: "yes"
Claude: "Added validation (30 lines)"
You: "yes"
...
Claude: "All tasks complete, tests passing"
You: "Perfect!"
Time: 45 minutes, clear progress
```

## Tips for Success

### Writing Good PRDs

**Be specific:**
- ❌ "Add email processing"
- ✅ "Process emails from Gmail Pub/Sub webhooks, extract message IDs, queue for classification with Celery"

**Include constraints:**
- Security requirements
- Performance targets (10 emails/min)
- Integration points (existing auth module)
- Error handling expectations

**Reference existing patterns:**
- "Use same module structure as app/modules/auth/"
- "Follow encryption patterns from security-first.md"
- "Match testing patterns from existing tests/"

### Answering Clarifying Questions

**Use numbered/lettered responses:**
```
Claude: "Which approach?"
   a) Option A
   b) Option B

You: "a" (quick, clear)
```

**Provide context when needed:**
```
Claude: "How should we handle errors?"

You: "Log to Sentry and retry 3 times with exponential backoff.
This matches our existing error handling pattern."
```

### Reviewing Sub-Tasks

**Don't blindly say "yes":**
- Check if security patterns followed
- Verify tests are included
- Ensure error handling present
- Confirm module structure matches

**Give actionable feedback:**
- ❌ "This doesn't look right"
- ✅ "Use encrypt_token() before storing, see security-first.md"

## File Organization

All PRDs and task lists save to `/tasks/`:

```
tasks/
├── 0001-prd-oauth-flow.md
├── tasks-0001-prd-oauth-flow.md
├── 0002-prd-gmail-webhooks.md
├── tasks-0002-prd-gmail-webhooks.md
├── 0003-prd-backlog-cleanup.md
└── tasks-0003-prd-backlog-cleanup.md
```

**Numbering:**
- PRDs: `0001-prd-feature-name.md`, `0002-prd-...`, etc.
- Tasks: `tasks-0001-prd-feature-name.md` (matches PRD number)

## Workflow Variations

### Quick Feature (Use simplified workflow)

For smaller features that still benefit from structure:

```
Create a quick PRD for [feature]:
[2-3 sentence description]

Then generate tasks and execute.
```

### Emergency Fix (Skip workflow)

For critical bugs:

```
Skip the PRD workflow and directly fix: [describe issue]
```

### Exploration (PRD only)

For research/planning:

```
Create a PRD for [feature] but don't generate tasks yet.
I want to review the requirements first.
```

## Common Mistakes to Avoid

### Mistake 1: Skipping PRD for Complex Features

```
❌ "Build the backlog cleanup feature"
✅ "Create a PRD for backlog cleanup feature, then generate tasks"
```

### Mistake 2: Saying "yes" Without Reviewing

```
❌ *blindly says yes to every sub-task*
✅ *actually reviews code, checks security patterns, verifies tests*
```

### Mistake 3: Vague Feature Descriptions

```
❌ "Add email stuff"
✅ "Add Gmail Pub/Sub webhook receiver with JWT verification and Celery task queuing"
```

### Mistake 4: Using Workflow for Simple Changes

```
❌ "Create PRD for fixing a typo in README.md"
✅ "Fix typo in README.md" (just do it directly)
```

## Measuring Success

Track these metrics:

- **First-try accuracy**: Sub-tasks work without revisions
- **Time saved**: Compare to monolithic prompts
- **Bug rate**: Fewer bugs with structured approach
- **Code quality**: More consistent patterns

## Quick Reference

### PRD Creation Template
```
I want to build [feature].
Use @ai-dev-tasks/create-prd.md to create a PRD.

[Problem it solves]
[Who uses it]
[Key functionality]
[Constraints/requirements]

Reference @CLAUDE.md for context.
```

### Task Generation Template
```
Take @tasks/[prd-file].md and create tasks using @ai-dev-tasks/generate-tasks.md
```

### Task Execution Template
```
Start on task 1.1 from the generated task list.
After reviewing, I'll say "yes" to continue.
```

## Related Skills

- **fastapi-module-builder.md** - Module patterns for implementation
- **security-first.md** - Security patterns to apply during execution
- **testing-requirements.md** - Tests to write for each task
- **git-workflow.md** - Committing after task completion
- **railway-deployment.md** - Deploying after all tasks complete
