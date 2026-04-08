# aggora-chat

`aggora-chat` is a Django-based community platform in the style of a modern, server-rendered Reddit-like product.

Primary production domain:

- `https://aggora.org`

Legacy / migration domain:

- `https://aggora.kolibri-kollektiv.eu`

Current production routing:

- `https://www.aggora.org` is intended to redirect permanently to `https://aggora.org`
- Cloudflare Tunnel terminates the public hostname and forwards the web app to the stack on port `18080`

The app currently includes:

- community feeds, discovery and profiles
- votes, saves, comments and polls
- moderation queue, mod log, bans and mod mail
- public and authenticated REST API endpoints
- invite links, onboarding, suggested communities and growth pages
- community challenges, notifications and share-card pages
- Google and GitHub social sign-in
- PWA manifest/service worker shell
- live Markdown preview for post and community creation

## Quick Start

Recommended contributor path with Docker:

```bash
just up
```

That one command will:

- create `.env` from [`.env.example`](/srv/projects/web/aggora-chat/.env.example) if it does not exist
- build and start the local Docker stack from [docker-compose.local.yml](/srv/projects/web/aggora-chat/docker-compose.local.yml)
- start local Postgres on `localhost:5432`
- auto-run migrations and demo seeding
- start MinIO and the local Nginx proxy
- print the local app URL when the stack is healthy

Then open:

```text
http://127.0.0.1:18080/
```

If you want to customize ports or credentials first, use two commands instead:

```bash
cp .env.example .env
just up
```

Useful Docker dev commands:

```bash
just local-up
just local-logs
just local-down
just local-ps
just local-minio-console-url
just db-export
FORCE=1 just db-import
just db-import-latest
just media-export
just media-import-latest
```

Detailed onboarding for contributors is documented in [docs/local-development-workflow.md](/srv/projects/web/aggora-chat/docs/local-development-workflow.md).

## Setup

The project uses `uv` for local Python dependency management.

1. Install dependencies:

```bash
just sync
```

2. Create your local environment file:

```bash
cp .env.example .env
```

The checked-in example is intentionally local-safe:

- no Docker-only Postgres host defaults
- no Redis requirement for cache or background jobs
- plain local `manage.py` commands require a Postgres connection via `DATABASE_URL` or `POSTGRES_*`

Then configure Postgres before running plain local Django commands.
The Docker flows (`just up`, `just local-up`) already provide the database container automatically.

3. Apply database migrations:

```bash
uv run python manage.py migrate
```

4. Optional: load demo/seed data:

```bash
uv run python manage.py seed
```

## Run

Start the development server:

```bash
uv run python manage.py runserver
```

If you want the full stack with supporting services, there are two Docker compose files in the repo:

- `docker-compose.local.yml`
- `docker-compose.prod.yml`

The compose files inject container-friendly defaults themselves, so local `.env` values do not need to point at a Docker-only database host unless you want that behavior outside Docker.
The default stack is now SQL-first and runs without Redis.

### Docker Files

Recommended for contributors:

- [docker-compose.local.yml](/srv/projects/web/aggora-chat/docker-compose.local.yml): stable Docker-based local development stack with Postgres, MinIO, proxying, migrations, and seed data
- [docker-compose.prod.yml](/srv/projects/web/aggora-chat/docker-compose.prod.yml): production deployment stack for `aggora.org` and related public environments
- [`.env.example`](/srv/projects/web/aggora-chat/.env.example): shared local environment template used by both Docker and plain `uv` workflows
- [scripts/bootstrap-local-docker.sh](/srv/projects/web/aggora-chat/scripts/bootstrap-local-docker.sh): helper used by `just up` and `just local-up`

### Database Dumps

The contributor Docker flow also supports safer Postgres custom-format dumps:

```bash
just db-export
FORCE=1 just db-import
just db-import-latest
```

This creates binary Postgres dumps in `dumps/` using `pg_dump -Fc` and restores them with `pg_restore --clean --if-exists`.

Useful variants:

```bash
DUMP_FILE=dumps/agora-latest.dump FORCE=1 just db-import
just db-dump-list
just db-shell
```

### Media Archives

Uploaded avatars, banners, and post images live under `media/`, not in Postgres, so they need a separate backup/restore flow:

```bash
just media-export
FORCE=1 just media-import
just media-import-latest
```

This creates tar.gz archives in `dumps/` and restores them back into the local `media/` directory used by the Docker dev stack.

Useful variants:

```bash
ARCHIVE_FILE=dumps/media-latest.tar.gz FORCE=1 just media-import
just media-list
```

Alternative image-based bootstrap:

For the local Docker path with Postgres, migrations, and seed data:

```bash
just local-up
```

Equivalent direct Docker Compose command:

```bash
docker compose --env-file .env -f docker-compose.local.yml up --build -d
```

The local bootstrap will:

- create `.env` from [`.env.example`](/srv/projects/web/aggora-chat/.env.example) if it does not exist
- build and start [`docker-compose.local.yml`](/srv/projects/web/aggora-chat/docker-compose.local.yml)
- wait for the app to respond through the local Nginx proxy
- start MinIO and run the one-shot bucket initializer automatically
- print the MinIO Console URL and credentials from `.env`
- start a local Postgres container on `localhost:5432`
- auto-run migrations and demo seeding through the container entrypoint

That stack exposes:

- app: `http://127.0.0.1:18080/`
- health: `http://127.0.0.1:18080/healthz/`
- MinIO Console: `http://127.0.0.1:19001/`
- Postgres: `localhost:5432`

Useful local Docker commands:

```bash
just local-logs
just local-ps
just local-down
just local-minio-console-url
just media-variants-backfill-dry-run
just media-variants-backfill
just media-variants-cleanup-dry-run
just media-variants-cleanup
```

Media originals are now stored under `original/...`, and responsive WebP variants are generated under:

- `optimized/webp/sm/...`
- `optimized/webp/md/...`
- `optimized/webp/lg/...`

For production routing with Cloudflare Tunnel, see [`docs/cloudflare-migration-aggora-org.md`](/srv/projects/web/aggora-chat/docs/cloudflare-migration-aggora-org.md).

## Test

Two runners are supported:

```bash
just test
```

or

```bash
just pytest
```

Additional useful commands:

```bash
just lint
just format
```

`pytest.ini` points at `config.settings.test`, and `requirements-dev.txt` includes both `pytest` and `pytest-django`.

## Env

Plain local `uv` workflows and the Docker contributor flow both use `.env`.

Commonly relevant variables:

- `DJANGO_ENV`, `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`
- `APP_NAME`, `APP_TAGLINE`, `APP_PUBLIC_URL`
- `SEED_USERS_FILE`, `SEED_ADMINS_FILE`
- `AUTO_MIGRATE_ON_START`, `AUTO_SEED_ON_START`, `SEED_SKIP_DEMO_CONTENT`
- `DATABASE_URL` or the `POSTGRES_*` fallback variables
- `CELERY_TASK_ALWAYS_EAGER`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`
- `EMAIL_DELIVERY_MODE`, `DJANGO_DEFAULT_FROM_EMAIL`

Use [`.env.example`](/srv/projects/web/aggora-chat/.env.example) as the single onboarding template for both Docker and plain local `uv` workflows.

## Seed Data

The project ships with JSON-backed demo seed data and helper commands:

- `uv run python manage.py seed`
- `uv run python manage.py seed --skip-demo-content`
- `uv run python manage.py create_test_user`
- `uv run python manage.py sync_staff_accounts`

Canonical seed sources:

- [`data/seed/users.json`](/srv/projects/web/aggora-chat/data/seed/users.json): 5 demo users
- [`data/seed/admins.json`](/srv/projects/web/aggora-chat/data/seed/admins.json): 2 admin accounts
- [`docs/test-accounts.md`](/srv/projects/web/aggora-chat/docs/test-accounts.md): human-readable credentials list
- [`docs/seeding.md`](/srv/projects/web/aggora-chat/docs/seeding.md): seeding workflow and container startup behavior

The main seeded community is `c/freya-seed-lounge`. The seed command is idempotent and can be re-run safely.

Use a custom seed file set if needed:

```bash
uv run python manage.py seed --file data/seed/users.json --admins-file data/seed/admins.json
```

Docker Compose now auto-runs migrations and demo seeding on container start by default. Control it with:

```bash
AUTO_MIGRATE_ON_START=1
AUTO_SEED_ON_START=1
SEED_SKIP_DEMO_CONTENT=0
```

## Architecture

The app is organized as a Django monolith with domain apps:

- `apps/accounts`: user model, handle onboarding, follow/block, notifications
- `apps/communities`: communities, memberships, invites, wiki, landing pages, challenges
- `apps/posts`: posts, comments, polls, crossposts and posting flows
- `apps/votes`: votes and saved posts
- `apps/feeds`: home/popular/community feed rendering
- `apps/search`: SQL/Elasticsearch-backed discovery and search
- `apps/moderation`: reports, queue, mod actions, bans, mod mail, agent moderation plumbing
- `apps/api`: REST endpoints for feeds, posts, voting, comments and agent moderation
- `apps/common`: shared utilities, markdown rendering, branding context and health checks

Technical direction:

- Django server-rendered templates
- HTMX for lightweight interactive updates
- Tailwind-driven UI styling
- optional Elasticsearch for search
- SQL-first local/dev runtime with eager task execution by default

## API

Base path:

- `/api/v1/`

Main endpoints:

- `GET /api/v1/popular/`
- `GET /api/v1/c/<slug>/feed/`
- `GET /api/v1/posts/<id>/`
- `GET /api/v1/posts/<id>/comments/`
- `POST /api/v1/posts/`
- `POST /api/v1/comments/`
- `POST /api/v1/vote/`
- `GET /api/v1/search/?q=...`
- `GET /api/v1/u/<handle>/`
- `GET /api/v1/u/<handle>/posts/`
- `POST /api/v1/mod/<community_slug>/action/`

Example: popular feed

```bash
curl http://127.0.0.1:8000/api/v1/popular/
```

Example: search posts

```bash
curl "http://127.0.0.1:8000/api/v1/search/?q=policy&sort=top"
```

Example: create a post with token auth

```bash
curl -X POST http://127.0.0.1:8000/api/v1/posts/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "community_slug": "agora-builders",
    "post_type": "text",
    "title": "Hello Agora",
    "body_md": "First post from the API"
  }'
```

Example: vote on a post

```bash
curl -X POST http://127.0.0.1:8000/api/v1/vote/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "post_id": 1,
    "value": 1
  }'
```

Example: agent moderation action

```bash
curl -X POST http://127.0.0.1:8000/api/v1/mod/agora-builders/action/ \
  -H "Authorization: Token AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "remove",
    "post_id": 42,
    "confidence": 0.97,
    "reason_code": "spam",
    "explanation": "High-confidence spam pattern"
  }'
```

## Known Access Rules

- `public` communities can be joined directly
- `restricted` communities are publicly viewable but require invites or approval to join
- `private` communities are visible only to members

## Known Gaps

- API search currently indexes posts only; the web search page also surfaces quick community and profile matches
- Screenshot artifacts are not committed automatically and should be regenerated after UI changes
- Full test execution still depends on installing local Python dependencies first
- Some growth and notification flows are app-level only; mail/push delivery is not yet a complete production notification system
- Moderation actions are now symmetric for lock/sticky, but moderator UX can still be expanded further

## PWA

The app now ships with a lightweight installable shell:

- `/manifest.webmanifest`
- `/service-worker.js`

It covers install metadata and basic shell caching for the main feed surfaces. This is intentionally minimal and can be extended later with push delivery or deeper offline support.

## Screenshots

`output/gui-screenshots/` should contain freshly generated UI captures only.

Regenerate them after notable UI changes with:

```bash
uv run python scripts/generate_screenshots.py
```
