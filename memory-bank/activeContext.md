# Active Context - Lumigen

## Current Work Focus
- Gallery UI improvements (click-to-select, button positioning)
- Refactoring according to .clinerules

## Recent Changes
1. **Session Navigation**: Added time-based categorization (today, this week, older) with max 30 days
2. **Session Age Display**: Shows "Xh" for today/yesterday, "Xd", "Xw", "Xm" for older
3. **App Version**: Version displayed in footer with copyright "2026 by Jean Schmitz"
4. **JavaScript Refactoring**: Moved inline JS to `app/web/static/js/app.js`
5. **Tailwind Config**: Moved to separate `tailwind-config.js` file
6. **Gallery Selection**: Changed from checkbox to click-to-select with visible ring
7. **Gallery Hover**: Buttons moved to bottom, blur overlay fixed
8. **Pydantic Schemas**: Created `app/schemas/` with validation schemas

## Next Steps
- Apply Pydantic schemas to API endpoints in `app/main.py`
- Add docstrings to public API functions
- Consider dependency injection for services

## Important Patterns
- HTMX for SPA-like page updates without full reloads
- TailwindCSS via CDN with custom config
- SQLite database with SQLAlchemy ORM
- Jinja2 templates with fragment includes

## Learnings
- Gallery click-to-select required handling of event propagation
- Tailwind safelist needed for dynamic classes
- Pydantic schemas provide centralized validation
