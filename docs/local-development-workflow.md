# Local Development Workflow

This guide is the recommended Docker-based onboarding path for local contributors.

## Prerequisites

- Docker with `docker compose`
- free local ports:
  - `18080` for the app
  - `19001` for the MinIO Console
  - `5432` for Postgres

## Fast Start

Clone the repo, then run:

```bash
cp .env.example .env
just up
```

That starts the local stack defined in [docker-compose.local.yml](/srv/projects/web/aggora-chat/docker-compose.local.yml).

## What Starts

The local stack includes:

- `nginx`
- `web`
- `db`
- `minio`
- `minio-init`

The app uses:

- Postgres for the database
- MinIO for media storage
- Nginx as the local reverse proxy

## Local URLs

After startup, open:

- App: `http://127.0.0.1:18080/`
- Health: `http://127.0.0.1:18080/healthz/`
- MinIO Console: `http://127.0.0.1:19001/`

## Useful Commands

Start or rebuild:

```bash
just up
```

or:

```bash
docker compose --env-file .env -f docker-compose.local.yml up --build -d
```

Inspect the stack:

```bash
just local-ps
just local-logs
```

Stop the stack:

```bash
just local-down
```

Show the MinIO Console URL:

```bash
just local-minio-console-url
```

## Database And Media Helpers

Create a database dump:

```bash
just db-export
```

Restore the latest dump:

```bash
FORCE=1 just db-import-latest
```

Create a media archive:

```bash
just media-export
```

Restore the latest media archive:

```bash
FORCE=1 just media-import-latest
```

## Typical Fresh-Machine Test

To verify the local setup on another developer machine:

```bash
git pull
cp .env.example .env
docker compose --env-file .env -f docker-compose.local.yml up --build -d
docker compose --env-file .env -f docker-compose.local.yml ps
curl http://127.0.0.1:18080/healthz/
```

Expected result:

- containers are `Up`
- `/healthz/` returns `200`

## Troubleshooting

If startup fails:

```bash
docker compose --env-file .env -f docker-compose.local.yml logs -f nginx web db minio
```

If ports are already in use, adjust them in [`.env.example`](/srv/projects/web/aggora-chat/.env.example) or your local `.env`.
