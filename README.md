# pisspoor

The app behind [pisspooridea.com](https://pisspooridea.com) (agency) and
[pisspooridea.lol](https://pisspooridea.lol) (guerrilla site): a restroom QR ad network.
Venues sign up, we stick QR codes in their bathrooms, patrons scan, and ad revenue is
split across venues by traffic.

Deploys to the wielandtech homelab via GitOps; see [AGENTS.md](AGENTS.md).

## Local development

```bash
uv venv --python 3.13 .venv
uv pip install -r requirements-dev.txt --python .venv/Scripts/python.exe
SECRET_KEY=local-dev DEBUG=1 .venv/Scripts/python manage.py migrate
SECRET_KEY=local-dev DEBUG=1 .venv/Scripts/python manage.py runserver 8080
```

Before pushing: `ruff check . && ruff format --check . && pytest`.

## Configuration

All environment variables: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
`DATABASE_*` (SQLite when `DATABASE_NAME` is unset), `PUBLIC_BASE_URL`, `FUN_HOSTS`, `AGENCY_URL`, `ADMIN_HOSTS`, `OPERATOR_LEGAL_NAME`, `LEGAL_EMAIL`, `EMAIL_HOST`/`EMAIL_PORT`/`EMAIL_USE_SSL`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`/`DEFAULT_FROM_EMAIL`, `NTFY_URL`/`NTFY_PUBLIC_URL`/`NTFY_TOKEN`, `SCAN_HASH_SECRET`,
`TIME_ZONE`, `LOG_LEVEL`, `SECURE_SSL_REDIRECT`.
