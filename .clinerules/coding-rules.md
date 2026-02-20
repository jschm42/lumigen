## Coding Guidelines

### Clean Code & Architecture
- Separate concerns: routers for HTTP, services for business logic, repositories for data access
- Single Responsibility: one function does one thing, keep functions under 20 lines
- Use repository pattern for all database access
- Models are data structures only, no business logic
- Extract common logic into utilities, avoid code duplication
- Use data classes when functions need more than 3 parameters

### Strict Separation
- Never use inline style attributes
- Never use inline event handlers like onclick
- Never use script tags in templates except for external CDN
- CSS goes in separate files in static folder
- JavaScript goes in separate files with event delegation
- Templates are for structure and logic only
- Serve static assets via FastAPI StaticFiles

### What to Comment
- Docstrings for all public functions and classes using Google style
- Complex algorithms explaining WHY not WHAT
- Workarounds with ticket references
- Use type hints instead of comments for types

### What Not to Comment
- Obvious code, use self-explanatory names instead
- Repetition of code in words
- Commented out code, use git instead


## Security

### Security Requirements
- Never log sensitive data like passwords, tokens, or API keys
- Never build SQL queries manually, use SQLAlchemy ORM exclusively
- Always validate input using Pydantic schemas
- Always use environment variables for secrets via pydantic-settings
- Always configure HTTPS for production
- Never store plaintext passwords, use bcrypt or argon2
- Validate file extensions AND mime types for uploads
- Limit file upload sizes
- Store uploaded files outside webroot
- Implement rate limiting on APIs
- Configure CORS properly
- Use timeouts with httpx
- Validate tokens server-side


## Dependency Best Practices

### FastAPI
- Use dependency injection for shared resources
- Use async/await consistently
- Define response models with Pydantic
- Register exception handlers centrally

### SQLAlchemy
- Use Alembic for all schema changes
- Handle sessions via dependency injection
- Be conscious of lazy loading
- Avoid N+1 queries using joinedload or selectinload

### Pydantic
- Use schemas for request and response
- Use BaseSettings for configuration
- Create custom validators for complex validation
- Use Field for metadata

### Jinja2
- Keep auto-escaping enabled for XSS protection
- Use template inheritance for DRY
- Use macros for reusable components
- No business logic in templates

### httpx
- Always set timeouts
- Use async client for performance
- Handle network errors
- Configure base URL centrally
- Pre-Commit Checklist
- No hardcoded credentials
- All inputs validated
- Separation of concerns maintained
- No inline styles or scripts
- Docstrings present
- Type hints set
- Alembic migration created for database changes

### Performance
- Use async database queries where possible
- Use SQLAlchemy connection pooling defaults
- Cache static files with Cache-Control headers
- Lazy load and cache Pillow images
- Cache HuggingFace models locally
