# Detailed Implementation Plan

Dieses Dokument ueberfuehrt das abgestimmte Implementierungskonzept in eine repo-lokale Referenz fuer die Umsetzung.

## Architekturueberblick

- Browser mit serverseitig gerenderten Django-Seiten
- HTMX fuer partielle Updates
- PostgreSQL als Source of Truth
- Elasticsearch fuer Suche und spaetere Feed-Read-Optimierung
- Redis fuer Cache, Rate Limiting und Celery Broker
- Celery fuer asynchrone Verarbeitung

## Projektstruktur

Angestrebte Struktur:

- `config/` fuer Django-Settings, URLs, ASGI/WSGI und Celery
- `apps/accounts/`
- `apps/communities/`
- `apps/posts/`
- `apps/votes/`
- `apps/moderation/`
- `apps/search/`
- `apps/feeds/`
- `apps/api/`
- `templates/`
- `static/`

## Kernentscheidungen

- Postgres-first fuer alle Writes
- Search und spaeter skalierbare Feeds ueber Elasticsearch
- HTMX statt SPA fuer die primare Web-Interaktion
- Tailwind fuer konsistente, dichte UI
- Pseudonyme Identitaet ueber `handle`
- Agentenmoderation nur mit Audit Trail und klaren Permissions

## Umsetzungsphasen

- Phase 1: Foundation
- Phase 2: Core Content
- Phase 3: Moderation Foundation
- Phase 4: Agent Moderation
- Phase 5: Search And Discovery
- Phase 6: API And Polish
- Phase 7: Scale Prep

Weitere Details je Phase liegen unter `requirements/phases/`.
