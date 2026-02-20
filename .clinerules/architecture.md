## Architecture

- Separate concerns: routers for HTTP, services for business logic, repositories for data access
- Single Responsibility: one function does one thing, keep functions under 20 lines
- Use repository pattern for all database access
- Models are data structures only, no business logic
- Extract common logic into utilities, avoid code duplication
- Use data classes when functions need more than 3 parameters

