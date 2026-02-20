# Project Brief - Lumigen

## Core Purpose
Lumigen is a local AI image generation control room. It provides a web-based interface for managing AI image generation with support for multiple providers (OpenAI, OpenRouter, Google, BFL).

## Key Features
- **Profile Management**: Create and manage generation profiles with different providers and settings
- **Chat Interface**: Interactive generation with session history
- **Gallery**: Browse and manage generated images with filtering and categorization
- **Admin Panel**: Configure providers, models, dimension presets, and enhancement settings

## Technology Stack
- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: TailwindCSS + HTMX + Jinja2
- **Image Processing**: Pillow for thumbnails
- **AI Providers**: OpenAI, OpenRouter, Google, BFL adapters

## Current Status
- MVP complete with all core features working
- Session pagination with time categorization (today, this week, older)
- Gallery with bulk actions (select by click, bulk delete, bulk categorize)
- Refactoring in progress (Pydantic schemas added)
