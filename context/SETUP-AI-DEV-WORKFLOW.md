# Setup Guide: Ryan Carson's AI Dev Workflow

## Overview

This workflow adds structured task management to your development process. It works alongside your existing `claude.md` file.

**Your `claude.md`** = Project context (what you're building, architecture, constraints)  
**This workflow** = Task orchestration (how to break work into reviewable pieces)

---

## 1. Initial Setup

### Clone the workflow files

```bash
cd inbox-janitor
git clone https://github.com/snarktank/ai-dev-tasks.git
mkdir tasks
```

### Update your claude.md

Add this section at the **very top** of your `claude.md` file:

```markdown
# AI Dev Workflow Commands

When building new features, use this 3-step structured workflow:

**Step 1: Create PRD**
```
I want to build [feature name].
Use @ai-dev-tasks/create-prd.md to create a PRD.

[Describe your feature here]

Reference @claude.md for architecture context.
```

**Step 2: Generate Tasks**
```
Take @tasks/[your-prd-file].md and create tasks using @ai-dev-tasks/generate-tasks.md
```

**Step 3: Execute Tasks**
```
Start on task 1.1 and use @ai-dev-tasks/process-task-list.md
```

All PRDs and task lists save to `/tasks` directory.

---
```

---

## 2. File Structure (After Setup)

```
inbox-janitor/
├── claude.md                           # Your existing project context
├── ai-dev-tasks/                      # Ryan's workflow (cloned)
│   ├── create-prd.md                  # Step 1: Feature planning
│   ├── generate-tasks.md              # Step 2: Break into tasks
│   └── process-task-list.md           # Step 3: Execute one-by-one
└── tasks/                             # Generated files go here
    ├── 0001-prd-[feature-name].md     # PRD (created in step 1)
    └── tasks-0001-prd-[feature-name].md  # Task list (created in step 2)
```

---

## 3. How to Use It (3-Step Process)

### Step 1: Create a PRD

**Prompt:**
```
I want to build [feature name].
Use @ai-dev-tasks/create-prd.md to create a PRD.

[Describe your feature in detail - be specific about:
- What problem it solves
- Who will use it
- Key functionality needed]

Reference @claude.md for architecture context.
```

**What happens:**
- Claude asks clarifying questions
- Answer them (use numbered lists to respond quickly)
- Claude generates a PRD
- Saves to `/tasks/0001-prd-[feature-name].md`

---

### Step 2: Generate Tasks from PRD

**Prompt:**
```
Take @tasks/0001-prd-[feature-name].md and create tasks using @ai-dev-tasks/generate-tasks.md
```

**What happens:**
- Claude shows you 5-7 high-level parent tasks
- You say "Go"
- Claude generates detailed sub-tasks under each
- Lists relevant files to create/modify
- Saves to `/tasks/tasks-0001-prd-[feature-name].md`

---

### Step 3: Execute Tasks (One at a Time)

**Prompt:**
```
Start on task 1.1 and use @ai-dev-tasks/process-task-list.md
```

**What happens:**
- Claude does ONE sub-task
- Waits for your "yes" (or "y") to continue
- Runs tests after completing each parent task
- Commits changes with good messages
- Moves to next task only after your approval

**Your job:** Review each change, say "yes" if good, give feedback if not.

---

## 4. Example Workflow (OAuth Feature)

### Step 1: Create PRD
```
I want to build the OAuth flow for Gmail.
Use @ai-dev-tasks/create-prd.md to create a PRD.

From my roadmap (Week 1-2 Foundation):
- Gmail OAuth using Authlib
- Store encrypted tokens (Fernet)
- Token refresh handling
- Web callback endpoint

This is the foundation for all email access.
Security is critical - see claude.md security section.

Reference @claude.md for architecture context.
```

### Step 2: Generate Tasks
```
Take @tasks/0001-prd-oauth-gmail.md and create tasks using @ai-dev-tasks/generate-tasks.md
```

### Step 3: Execute
```
Start on task 1.1 and use @ai-dev-tasks/process-task-list.md
```

Then just say "yes" after reviewing each sub-task completion.

---

## 5. Why This Helps

**Without workflow:**
```
You: "Build OAuth for Gmail"
Claude: [Generates 500 lines of code across 10 files]
You: "Wait, this doesn't match my security requirements..."
```

**With workflow:**
```
You: "Build OAuth for Gmail" → PRD → Tasks → Execute
Claude: "Task 1.1: Create OAuth config module (20 lines)"
You: "yes"
Claude: "Task 1.2: Add token encryption (30 lines)"
You: "yes"
[etc... reviewable pieces]
```

**Benefits:**
- You control each step
- Catch issues early
- Claude stays focused
- Clear progress tracking
- Better code quality

---

## 6. Quick Reference

### When to use this workflow
- Building any feature from your roadmap
- Complex changes (>50 lines of code)
- Anything with multiple files or steps

### When NOT to use it
- Quick bug fixes
- Single-line changes
- Updating documentation
- Simple refactoring

### Tips for success
- Be specific in your initial feature description
- Answer PRD questions thoughtfully
- Actually review each sub-task (don't just say "yes" blindly)
- Give feedback when something's wrong
- Let Claude handle the task breakdown

---

## 7. Your Next Steps

**Option 1: Test it now**
Pick a small feature from your Week 1-2 roadmap and try the full workflow:
- OAuth flow (good first test)
- Email templates setup
- Token encryption module

**Option 2: Start with your current work**
Use it for whatever you're building next.

**Option 3: Read the workflow files first**
Open `ai-dev-tasks/create-prd.md` to see what Claude will ask you.

---

## Notes

- The workflow files work with Claude Code CLI (what you're using)
- Your `claude.md` stays as your main context file
- Generated PRDs and task lists go in `/tasks`
- You can modify the workflow files to fit your style
- This is the exact workflow from the YouTube video transcript you shared

---

## Troubleshooting

**If Claude doesn't ask clarifying questions:**
Make sure you're using `@ai-dev-tasks/create-prd.md` in your prompt.

**If files aren't saving to /tasks:**
Create the directory first: `mkdir tasks`

**If Claude does too many tasks at once:**
Remind it: "Use @ai-dev-tasks/process-task-list.md - do ONE sub-task at a time"

**If you want to customize:**
Edit the `.md` files in `ai-dev-tasks/` to match your preferences.
