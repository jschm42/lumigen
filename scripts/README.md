# Provider Config Key Scripts

- Bash: `./scripts/generate_provider_key.sh`
- PowerShell: `./scripts/generate_provider_key.ps1`

Both scripts print a Fernet key for `PROVIDER_CONFIG_KEY`.

## Docker run/update scripts

The Docker helper scripts (`docker_run.*`, `docker_update.*`) read your repository `.env` and pass runtime env vars into the container.

For HTTPS deployments behind a reverse proxy, set these in `.env` before running the scripts:

- `SESSION_HTTPS_ONLY=true`
- `PROXY_HEADERS_ENABLED=true`
- `PROXY_HEADERS_TRUSTED_HOSTS=*` (or a specific trusted proxy list)

## Smoke checks

- Run quick route/template checks:

```bash
python scripts/smoke_web_routes.py
```

Validates key pages return `200` and that template JS refactors are loaded via external static files.
