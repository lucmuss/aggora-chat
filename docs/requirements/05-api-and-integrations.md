# API And Integrations

## API-Philosophie

Die API soll sich listing-first und Reddit-aehnlich anfuehlen:

- cursor-basierte Pagination statt Seitenzahlen
- einheitliche Listing-Responses
- stabile Read-Endpunkte fuer Feeds und Detailansichten
- klar abgegrenzte Write- und Moderationsendpunkte

## Listing-Format

Empfohlene Standardform:

```json
{
  "items": [],
  "after": null,
  "before": null,
  "count": 0
}
```

## MVP

### Read-Only Endpunkte

- `/api/v1/home`
- `/api/v1/c/<slug>/hot`
- `/api/v1/c/<slug>/new`
- `/api/v1/c/<slug>/rising`
- `/api/v1/c/<slug>/top`
- `/api/v1/c/<slug>/controversial`
- `/api/v1/posts/<id>`
- `/api/v1/posts/<id>/comments`

### Pagination

- `after`
- `before`
- `limit`
- `count`

### Auth fuer Write-Aktionen

- token-basierte Authentifizierung
- spaeter idealerweise OAuth2 oder OIDC-kompatibel

### Basis-Schutz

- Rate Limiting
- API Keys fuer Apps oder Agenten

## V1

### User-Endpunkte

- `/api/v1/u/<handle>/submitted`
- `/api/v1/u/<handle>/comments`
- `/api/v1/u/<handle>/saved`

### Suche

- `/api/v1/search?q=...`
- strukturierte Query-Operatoren

### Moderations-API

- Queue lesen
- Approve/Remove/Ban ausloesen
- Mod Log lesen
- Mod Mail Antworten schreiben

## Integrationsanforderungen

- API muss mobile und Third-Party-Clients unterstuetzen koennen
- Agent-Service-Accounts brauchen scope-beschraenkte Tokens
- Berechtigungsmodell muss fuer menschliche Mods und Agenten getrennt pruefbar sein

## Akzeptanzkriterien

- Feed- und Detaildaten sind ueber API abrufbar
- Pagination bleibt unter Veraenderung der Daten robust
- geschuetzte Write-Endpunkte sind sauber autorisiert
