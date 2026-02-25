# Provider Config Key Scripts

- Bash: `./scripts/generate_provider_key.sh`
- PowerShell: `./scripts/generate_provider_key.ps1`

Both scripts print a Fernet key for `PROVIDER_CONFIG_KEY`.

## Smoke checks

- Run quick route/template checks:

```bash
python scripts/smoke_web_routes.py
```

Validates key pages return `200` and that template JS refactors are loaded via external static files.
