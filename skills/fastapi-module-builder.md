# FastAPI Module Builder Skill

## Purpose
Build new modules in Inbox Janitor following the established modular monolith pattern.

## Project Structure

Inbox Janitor uses a **modular monolith** architecture (NOT microservices). Each module is self-contained but shares database and core utilities.

```
app/
├── core/              # Shared utilities
│   ├── config.py      # Pydantic settings
│   ├── database.py    # SQLAlchemy setup
│   └── security.py    # Encryption, JWT
├── modules/           # Domain modules
│   ├── auth/          # OAuth flows
│   ├── ingest/        # Gmail webhooks
│   ├── classifier/    # Email classification
│   ├── executor/      # Actions (archive/trash)
│   ├── digest/        # Email templates
│   └── billing/       # Stripe integration
├── models/            # SQLAlchemy models
└── tasks/             # Celery background jobs
```

## Creating a New Module

### Step 1: Module Folder Structure

```
app/modules/{module_name}/
├── __init__.py        # Empty or exports
├── routes.py          # FastAPI endpoints
├── service.py         # Business logic
└── schemas.py         # Pydantic models (optional)
```

### Step 2: Routes Pattern

Every route file should follow this pattern:

```python
"""
{Module Name} routes - {Brief description}

Endpoints:
- GET /endpoint-name - Description
- POST /endpoint-name - Description
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import User, Mailbox  # Import relevant models

router = APIRouter(prefix="/{module}", tags=["{module}"])

@router.get("/")
async def get_items(db: AsyncSession = Depends(get_db)):
    """Docstring explaining endpoint purpose."""
    # Implementation
    pass
```

### Step 3: Service Layer Pattern

Business logic goes in `service.py`:

```python
"""
{Module Name} service - Business logic for {module}.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User


async def get_user_by_email(db: AsyncSession, email: str):
    """Get user by email address."""
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()
```

### Step 4: Register Router in main.py

```python
# app/main.py
from app.modules.{module}.routes import router as {module}_router

app.include_router({module}_router)
```

## Database Models

### Model Pattern

All models follow these conventions:

```python
"""
{ModelName} model - {Description}

{Any critical notes about the model}
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ModelName(Base):
    """Brief description."""
    
    __tablename__ = "table_name"
    
    # Standard fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign keys (if any)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Other fields
    field_name = Column(String, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="table_name")
    
    def __repr__(self):
        return f"<ModelName {self.id}>"
```

### Database Conventions

- **Primary Keys**: Always `UUID` (uuid.uuid4)
- **Timestamps**: `created_at`, `updated_at` (if needed)
- **Foreign Keys**: Include `ondelete="CASCADE"` and `index=True`
- **Nullable**: Explicitly set `nullable=True/False`
- **Relationships**: Define back_populates on both sides
- **Indexes**: Add to frequently queried fields

## Async Database Sessions

### Pattern 1: FastAPI Dependency Injection

```python
from app.core.database import get_db

@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()
```

### Pattern 2: Manual Session (Celery Tasks)

```python
from app.core.database import AsyncSessionLocal

async def background_task():
    async with AsyncSessionLocal() as session:
        try:
            # Do work
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

## Common Patterns

### Pattern: Check if Record Exists

```python
result = await db.execute(
    select(User).where(User.email == email)
)
user = result.scalar_one_or_none()

if not user:
    raise HTTPException(status_code=404, detail="User not found")
```

### Pattern: Create with Relationship

```python
user = User(email=email)
db.add(user)
await db.flush()  # Get user.id

mailbox = Mailbox(user_id=user.id, email_address=email)
db.add(mailbox)
await db.commit()
```

### Pattern: Update Record

```python
result = await db.execute(
    select(Mailbox).where(Mailbox.id == mailbox_id)
)
mailbox = result.scalar_one_or_none()

if mailbox:
    mailbox.is_active = False
    await db.commit()
```

## Error Handling

### Pattern: HTTP Exceptions

```python
from fastapi import HTTPException

# 404 Not Found
if not record:
    raise HTTPException(status_code=404, detail="Resource not found")

# 400 Bad Request
if not valid:
    raise HTTPException(status_code=400, detail="Invalid input")

# 500 Internal Error (catch-all)
try:
    # risky operation
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```

## Celery Tasks (Background Jobs)

### Task Pattern

```python
"""
{Module} tasks - Background jobs for {module}.
"""

from app.tasks.celery_app import celery_app
from app.core.database import get_sync_db

@celery_app.task(name="module.task_name")
def process_something(user_id: str):
    """Process something in background."""
    with get_sync_db() as db:
        # Do work (use sync SQLAlchemy here)
        user = db.query(User).filter(User.id == user_id).first()
        # ... process
```

## Testing New Modules

Every new module should include:

1. **Unit tests**: `/tests/unit/test_{module}.py`
2. **Integration tests**: `/tests/integration/test_{module}_api.py`
3. **Security tests**: If handling sensitive data

Example test structure:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_endpoint(client: AsyncClient):
    response = await client.get("/module/endpoint")
    assert response.status_code == 200
```

## Before Creating a Module

Ask yourself:
1. Does this belong in an existing module?
2. Is this a new domain concept or an extension?
3. Will this module need its own database tables?
4. Does this need background processing (Celery)?

## Module Boundaries

**Good separation**: 
- `auth/` - OAuth flows only
- `ingest/` - Email ingestion only
- `classifier/` - Classification logic only

**Bad separation**: 
- `email/` - Too broad, split into ingest/classifier/executor
- `utils/` - Not a domain, goes in `core/`

## Quick Reference

**Import database session**: `from app.core.database import get_db`
**Import models**: `from app.models import User, Mailbox`
**Import config**: `from app.core.config import settings`
**Import security**: `from app.core.security import encrypt_token, decrypt_token`

## Testing New Modules

Every new module must include tests (see **testing-requirements.md**):

1. **Unit tests**: `/tests/unit/test_{module}.py`
2. **Integration tests**: `/tests/integration/test_{module}_api.py`
3. **Security tests**: If handling sensitive data (see **security-first.md**)

## Deployment

After creating a module:
1. Run tests (see **testing-requirements.md**)
2. Commit with proper message (see **git-workflow.md**)
3. Push and verify Railway deployment (see **railway-deployment.md**)

## When Unsure

Reference existing modules:
- `/app/modules/auth/` - Complete OAuth implementation
- `/app/models/` - Model patterns and relationships
- `/CHANGELOG.md` - Architecture decisions

## Related Skills

- **security-first.md** - Security patterns for modules handling sensitive data
- **testing-requirements.md** - Required tests for new modules
- **railway-deployment.md** - Deploying new modules to production
- **git-workflow.md** - Committing module changes
- **ai-dev-workflow.md** - Use for complex multi-module features
