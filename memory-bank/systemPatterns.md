# System Patterns - Lumigen

## Architecture Overview
```
┌─────────────────────────────────────────────────┐
│                   FastAPI App                     │
├─────────────────────────────────────────────────┤
│  Routes (app/main.py)                           │
│  ├── /generate - Chat interface                  │
│  ├── /profiles - Profile management              │
│  ├── /gallery - Asset browser                   │
│  ├── /admin - Configuration                     │
│  └── /api/* - JSON APIs                        │
├─────────────────────────────────────────────────┤
│  Services (app/services/)                        │
│  ├── generation_service.py                      │
│  ├── gallery_service.py                         │
│  ├── enhancement_service.py                     │
│  ├── thumbnail_service.py                       │
│  └── upscale_service.py                        │
├─────────────────────────────────────────────────┤
│  Data Layer (app/db/)                          │
│  ├── models.py - SQLAlchemy models             │
│  ├── crud.py - Database operations              │
│  └── engine.py - Session management            │
├─────────────────────────────────────────────────┤
│  Providers (app/providers/)                      │
│  ├── base.py - Provider interface              │
│  ├── openai_adapter.py                         │
│  ├── openrouter_adapter.py                     │
│  ├── google_adapter.py                         │
│  └── bfl_adapter.py                           │
└─────────────────────────────────────────────────┘
```

## Design Patterns

### Service Pattern
All business logic in `app/services/`. Services are instantiated in `app/main.py` and used by routes.

### Repository Pattern
Database access through `app/db/crud.py`. All queries use SQLAlchemy ORM.

### Provider Adapter Pattern
AI providers implement common interface in `base.py`. Registry manages provider selection.

### Template Fragments
Reusable UI components in `app/web/templates/fragments/`. Used by main templates via Jinja2 inheritance.

## Component Relationships
- Routes depend on Services
- Services depend on Providers and DB
- Templates depend on Routes (via context)
- Static JS/CSS served via FastAPI StaticFiles

## Critical Paths
1. **Image Generation**: generate_submit → generation_service.create → provider.send_request → enqueue job
2. **Gallery Loading**: gallery_page → gallery_service.list_assets → render grid
3. **Session Pagination**: generate_page → build_session_items → paginate with offset/limit
