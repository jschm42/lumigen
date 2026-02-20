# Tech Context - Lumigen

## Technologies Used

### Backend
- **FastAPI**: Web framework with automatic OpenAPI docs
- **SQLAlchemy**: ORM for SQLite database
- **Pydantic**: Data validation and settings management
- **Alembic**: Database migrations

### Frontend
- **TailwindCSS**: Utility-first CSS framework (via CDN)
- **HTMX**: AJAX-based SPA alternative
- **Jinja2**: Template engine
- **Material Symbols**: Icon font

### Image Processing
- **Pillow**: Thumbnail generation and image processing
- **httpx**: Async HTTP client for provider APIs

## Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python -m app.main

# Run with Docker
docker build -t lumigen .
docker run -p 8010:8010 -v ./data:/app/data lumigen
```

## Dependencies (requirements.txt)
- fastapi
- uvicorn
- sqlalchemy
- pydantic-settings
- alembic
- pillow
- httpx

## Environment Variables
- `HOST`: Server host (default: 127.0.0.1)
- `PORT`: Server port (default: 8010)
- `UVICORN_RELOAD`: Enable auto-reload
- API keys for providers via admin UI or .env

## Tool Usage Patterns
- **Hot Reload**: Development server auto-reloads on file changes
- **Database**: SQLite stored in `./data/app.db`
- **Images**: Stored in `./data/images/`
- **Tailwind**: CDN version for development, custom safelist in config
