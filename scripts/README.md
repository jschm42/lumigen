# Provider Config Key Scripts

- Bash: `./scripts/generate_provider_key.sh`
- PowerShell: `./scripts/generate_provider_key.ps1`

Both scripts print a Fernet key for `PROVIDER_CONFIG_KEY`.

## Admin user reset script

Use this helper to create or reset an admin user in the local database.

```bash
python scripts/reset_admin_user.py --username admin
```

If `--password` is omitted, the script prompts securely and validates confirmation.

```bash
python scripts/reset_admin_user.py --username admin --password "your-new-password"
```

## Docker run/update scripts

The Docker helper scripts (`docker_run.*`, `docker_update.*`) read your repository `.env` and pass runtime env vars into the container.

Host and port can be configured in `.env`:
- `HOST=0.0.0.0` (default)
- `PORT=7003` (default)

For HTTPS deployments behind a reverse proxy, set these in `.env` before running the scripts:

- `SESSION_HTTPS_ONLY=true`
- `PROXY_HEADERS_ENABLED=true`
- `PROXY_HEADERS_TRUSTED_HOSTS=*` (or a specific trusted proxy list)

### Enabling built-in HTTPS

Run the SSL certificate generator to create a self-signed certificate:

- Bash: `./scripts/generate_ssl_cert.sh`
- PowerShell: `./scripts/generate_ssl_cert.ps1`

This creates `ssl/lumigen.crt` and `ssl/lumigen.key`. Then add these lines to your `.env`:

```
SSL_CERT_FILE=./ssl/lumigen.crt
SSL_KEY_FILE=./ssl/lumigen.key
```

The next `docker_run`/`docker_update` will mount the certificates and uvicorn will serve HTTPS directly.

## Smoke checks

- Run quick route/template checks:

```bash
python scripts/smoke_web_routes.py
```

Validates key pages return `200` and that template JS refactors are loaded via external static files.
