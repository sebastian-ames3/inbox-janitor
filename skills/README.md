# Claude Skills for Inbox Janitor

This folder contains 7 custom Claude Skills designed specifically for your Inbox Janitor development workflow.

## What Are Claude Skills?

Claude Skills are markdown files that teach Claude specialized knowledge about your project. They eliminate the need to repeat context in every conversation.

**Benefits:**
- 80% reduction in context-setting time
- Automatic enforcement of security requirements
- Consistent code patterns across all modules
- Faster development velocity
- Prevents common mistakes (token leaks, failed deployments, missing tests)

**Time Saved**: ~20 minutes per module × 15 modules = **5 hours**

---

## How to Use Skills

### Automatic Triggering
Skills are automatically activated when your request matches their domain:
- Creating modules → fastapi-module-builder.md
- Handling OAuth/tokens → security-first.md
- Deploying to Railway → railway-deployment.md
- Writing tests → testing-requirements.md
- Committing code → git-workflow.md

### Explicit References
You can also explicitly invoke a skill:
```
"Using the railway-deployment skill, deploy this to Railway"
"Following security-first skill, add OAuth endpoint"
"Using ai-dev-workflow skill, create a PRD for backlog cleanup"
```

### Integration with AI Dev Workflow
For complex features, combine skills with the structured PRD → Tasks → Execute workflow (see ai-dev-workflow.md).

---

## Skills Included

### 1. security-first.md ⭐️ **CRITICAL**

**Prevents:**
- OAuth token logging
- Email body storage in database
- Permanent email deletion
- SQL injection vulnerabilities

**Triggers when:**
- Creating new endpoints
- Handling OAuth/tokens
- Working with sensitive data
- Implementing email actions

### 2. fastapi-module-builder.md

**Teaches Claude:**
- Your exact module structure
- Database model patterns (UUID, relationships)
- Async session handling
- Router registration process

**Triggers when:**
- Creating new modules
- Adding endpoints
- Defining models
- Writing Celery tasks

### 3. email-classification.md

**Captures:**
- 3-tier classification system (Metadata → AI → User Rules)
- Delete vs Archive vs Keep logic
- Exception keywords (job, medical, bank, etc.)
- Safety rails and confidence thresholds

**Triggers when:**
- Implementing classifier
- Processing emails
- Writing classification logic
- Testing email handling

### 4. railway-deployment.md

**Teaches:**
- Environment variable management in Railway
- Deployment verification checklist
- Build and runtime log debugging
- Database migration workflow
- Health check monitoring

**Triggers when:**
- Deploying to Railway
- Debugging 502 errors
- Setting up environment variables
- Running migrations

### 5. testing-requirements.md

**Enforces:**
- Security tests before every commit
- Safety tests (no delete, undo flow, exception keywords)
- Test-driven development workflow
- Coverage requirements for critical code

**Triggers when:**
- Writing tests
- Creating security-critical features
- Implementing email actions
- Adding new endpoints

### 6. git-workflow.md

**Guides:**
- Commit message patterns
- Railway deployment verification steps
- When to wait for deployment success
- Pull request creation workflow

**Triggers when:**
- Committing code
- Creating pull requests
- Pushing to GitHub
- Deploying to production

### 7. ai-dev-workflow.md

**Structures:**
- PRD creation process
- Task generation from PRDs
- Step-by-step execution pattern
- When to use structured workflow vs. quick fixes

**Triggers when:**
- Building complex features
- Planning multi-step implementations
- Creating features from roadmap
- Need reviewable progress

---

## How Skills Work

### Before Skills:
```
You: "Create a classifier module"
Claude: [Creates basic structure]
You: "No, use UUID primary keys, async sessions, encrypt tokens..."
Claude: [Fixes]
You: "Follow our module structure..."
Claude: [Fixes again]
Time: 20 minutes
```

### After Skills:
```
You: "Create a classifier module"
Claude: [Reads skills, applies all patterns automatically]
You: "Perfect!"
Time: 2 minutes
```

---

## Maintaining Skills

Skills are living documentation that evolve with your codebase:

```bash
# Update a skill when patterns change
git add skills/
git commit -m "Update railway-deployment: add PostgreSQL backup verification"
git push
```

**When to update:**
- New security patterns emerge
- Architecture decisions change
- Testing requirements evolve
- Deployment process improves

---

## Integration with CLAUDE.md

Skills are referenced in the main CLAUDE.md file:

```markdown
## Claude Skills Reference

This project uses skills in `/skills/` for consistent patterns:
- **security-first.md** - OAuth, encryption, no body storage
- **fastapi-module-builder.md** - Module structure, DB patterns
- **email-classification.md** - 3-tier classification logic
- **railway-deployment.md** - Deployment verification
- **testing-requirements.md** - Security/safety tests
- **git-workflow.md** - Commits and Railway checks
- **ai-dev-workflow.md** - PRD → Tasks → Execute
```

---

## Success Metrics

Track these to measure impact:

**Week 1:**
- ✅ Skills committed to repo
- ✅ First module created using skills
- ✅ Zero security violations in new code

**Week 2:**
- ✅ 50% reduction in "fix this pattern" messages
- ✅ New modules match conventions first try

**Month 1:**
- ✅ 5+ hours saved in development time
- ✅ Consistent patterns across entire project

---

## FAQ

### Q: Do I need Claude Code for this?
**A:** No! Skills work in both Claude.ai (web) and Claude Code (CLI).

### Q: Should I commit skills to git?
**A:** YES! They're project documentation, not secrets.

### Q: Can I customize these skills?
**A:** Absolutely! Edit them to match your preferences.

### Q: How do I know if Claude is using a skill?
**A:** Claude Code will show "Reading security-first.md..." when triggered. You can also explicitly reference: "Using the security-first skill, create..."

### Q: Can I create more skills?
**A:** YES! As your project grows, add skills for:
- Gmail integration patterns
- Testing requirements
- Railway deployment
- Stripe billing
- Email templates

---

## Skill Trigger Reference

| Your Request | Triggered Skill(s) |
|-------------|-------------------|
| "Create new module" | fastapi-module-builder.md, testing-requirements.md |
| "Add OAuth endpoint" | security-first.md, testing-requirements.md |
| "Implement classifier" | email-classification.md, testing-requirements.md |
| "Deploy to Railway" | railway-deployment.md, git-workflow.md |
| "Write tests" | testing-requirements.md, security-first.md |
| "Create a PRD for X" | ai-dev-workflow.md |
| "Commit this code" | git-workflow.md |
| "Handle tokens" | security-first.md |

---

## FAQ

### Q: Do skills work in both Claude Code CLI and Claude.ai?
**A:** Yes! Skills auto-detect in Claude Code CLI. For Claude.ai, upload skill files to a Project.

### Q: Should skills be committed to git?
**A:** YES! They're project documentation, not secrets. Version them like code.

### Q: Can I edit these skills?
**A:** Absolutely! Skills should evolve with your codebase. Update them as patterns change.

### Q: How do I know if Claude used a skill?
**A:** Claude Code may show "Reading [skill].md..." You can also explicitly reference: "Using the security-first skill, create..."

### Q: Can I create more skills?
**A:** YES! As your project grows, add skills for:
- Stripe billing integration
- Postmark email templates
- Gmail API patterns
- Celery task patterns

---

## Next Steps

1. ✅ Skills are already set up in `/skills/`
2. Start using them: "Create a new module for email digest"
3. Watch for automatic pattern enforcement
4. Update skills as your patterns evolve

---

**Questions?** Skills are self-documenting - read the .md files themselves for detailed patterns!
