# Lumigen Frontend (React Migration)

Next.js 14 frontend that migrates core Lumigen views from server-rendered templates to React.

## Stack

- Next.js 14 + React 18
- next-intl (de/en routing)
- Prisma Client on existing SQLite DB
- react-hook-form + zod for validated forms
- Tailwind CSS

## Start

1. Install dependencies:

```bash
npm install
```

2. Copy env:

```bash
copy .env.example .env
```

3. Generate Prisma client:

```bash
npm run prisma:generate
```

4. Run dev server:

```bash
npm run dev
```

Default URL: `http://127.0.0.1:3100/de`

The backend is still FastAPI (`FASTAPI_BASE_URL`) and handles generation execution.
