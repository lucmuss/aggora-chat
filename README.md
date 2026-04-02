# aggora-chat

`aggora-chat` is a Django-based community platform in the style of a modern, server-rendered Reddit-like product.

Target domain:

- `https://aggora.kolibri-kollektiv.eu`

The app currently includes:

- community feeds, discovery and profiles
- votes, saves, comments and polls
- moderation queue, mod log, bans and mod mail
- public and authenticated REST API endpoints
- invite links, onboarding, suggested communities and growth pages
- community challenges, notifications and share-card pages

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

3. Apply database migrations:

```bash
uv run python manage.py migrate
```

4. Optional: load demo/seed data:

```bash
uv run python manage.py seed --skip-demo-content
```

## Run

Start the development server:

```bash
uv run python manage.py runserver
```

If you want the full stack with supporting services, there are also Docker compose files in the repo:

- `docker-compose.yml`
- `docker-compose.prod.yml`
- `docker-compose.stack.yml`

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

`pytest.ini` points at `config.settings.dev`, and `requirements/dev.txt` includes both `pytest` and `pytest-django`.

## Env

Environment values are loaded automatically from `.env`.

Commonly relevant variables:

- `DJANGO_ENV`, `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`
- `APP_NAME`, `APP_TAGLINE`, `APP_PUBLIC_URL`
- `DATABASE_URL` or the `POSTGRES_*` fallback variables
- `REDIS_CACHE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `SEARCH_BACKEND`, `SEARCH_INDEX_ENABLED`, `ELASTICSEARCH_URL`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `EMAIL_DELIVERY_MODE`, `DJANGO_DEFAULT_FROM_EMAIL`

Use [`.env.example`](/srv/projects/web/aggora-chat/.env.example) as the canonical starting point.

## Seed Data

The project ships with seed helpers and management commands:

- `uv run python manage.py seed --skip-demo-content`
- `uv run python manage.py create_test_user`
- `uv run python manage.py sync_staff_accounts`

Seed source files live under [`data/seed`](/srv/projects/web/aggora-chat/data/seed).

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
- Celery/Redis hooks for async recalculation and indexing

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

- Search currently indexes posts only; communities and user profiles are discovered through dedicated pages
- Screenshot artifacts are not committed automatically and should be regenerated after UI changes
- Full test execution still depends on installing local Python dependencies first
- Some growth and notification flows are app-level only; mail/push delivery is not yet a complete production notification system
- Moderation actions are now symmetric for lock/sticky, but moderator UX can still be expanded further

## Screenshots

`output/gui-screenshots/` should contain freshly generated UI captures only.

Regenerate them after notable UI changes with:

```bash
uv run python scripts/generate_screenshots.py
```
