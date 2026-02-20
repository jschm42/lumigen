## Security

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
