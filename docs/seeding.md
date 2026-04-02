# Seeding

This repository uses JSON-backed seed data for local development, screenshots, and QA.

## Canonical Seed Files

- [`data/seed/users.json`](/srv/projects/web/aggora-chat/data/seed/users.json)
  Contains 5 curated demo users.
- [`data/seed/admins.json`](/srv/projects/web/aggora-chat/data/seed/admins.json)
  Contains 2 admin accounts: one superuser and one moderator.
- [`docs/test-accounts.md`](/srv/projects/web/aggora-chat/docs/test-accounts.md)
  Lists all seeded credentials in a readable format.

## Default Local Workflow

```bash
uv run python manage.py migrate --noinput
uv run python manage.py seed
```

If you only want the accounts and memberships without starter posts/comments:

```bash
uv run python manage.py seed --skip-demo-content
```

## Docker Startup

The development `web` service enables automatic migrate + seed on container startup:

```env
AUTO_MIGRATE_ON_START=1
AUTO_SEED_ON_START=1
SEED_SKIP_DEMO_CONTENT=0
```

The image entrypoint respects those flags and otherwise does nothing automatically.

## What Gets Created

- 5 demo users
- 2 admin accounts
- `c/freya-seed-lounge`
- memberships for all seeded accounts
- starter intro posts and comments for the 5 demo users
