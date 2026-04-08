# Phase 02 Core Content

## Ziel

Agora bekommt in dieser Phase seine erste echte Diskussionsdynamik:

- Posts
- Kommentare
- Votes
- Home- und Community-Feeds
- vorbereitete Elasticsearch-Indexierung

## Scope

### Inhalte

- Textposts
- Linkposts
- Thread-Detailseite
- verschachtelte Kommentare

### Interaktionen

- Upvote und Downvote auf Posts und Kommentare
- Save und Unsave fuer Posts
- Auto-Upvote beim Erstellen von Post oder Kommentar

### Ranking

- Hot Score
- Sortierungen `hot`, `new`, `top`, `rising`

### Feed Layer

- PostgreSQL-basierte Feed-Queries als stabile Default-Quelle
- optionale Elasticsearch-Indexierung ueber Celery-Task

## Akzeptanzkriterien

- Nutzer koennen Posts erstellen und lesen
- Nutzer koennen Kommentare schreiben
- Votes wirken auf Score und Karma
- Home- und Community-Feed zeigen Posts mit Sortierung
- Search-Index-Hooks blockieren lokale Entwicklung nicht, wenn ES deaktiviert ist
