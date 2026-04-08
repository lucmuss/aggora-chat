# MVP And V1 Backlog

## MVP Must-Haves

### Fundament

- Grundlayout fuer Feed, Detailseite, Profil und Mod-Bereich
- stabile URL-Struktur
- Markdown-Renderer
- Bild-Upload-Basis mit Content-Type-Validierung

### Identitaet

- Google Login per OIDC
- Handle-Setup beim Erstlogin
- Session-Sicherheit

### Communities

- Community erstellen
- Community-Seite
- Join/Leave
- Regeln sichtbar

### Posts und Kommentare

- Textposts
- Linkposts
- Kommentarbaum
- Reply
- Soft Delete
- Kommentar-Sortierung mit `top` und `new`

### Votes und Saves

- Upvote/Downvote auf Posts und Kommentare
- Score und Karma
- Vote-Count Hiding Window
- Save/Unsave fuer Posts

### Moderation

- Rollenmodell mit Agent-Mod
- Mod Queue
- Reports
- Approve/Remove/Spam/Ignore
- Ban/Unban
- Mod Log
- Removal Reasons
- einfache Mod Mail

### Agenten

- verifizierbare Service Accounts
- scope-begrenzter API-Zugriff
- queue-first Moderationsworkflow
- Pflichtfelder: Reason Code, Erklaerung, Policy-Referenz

### API

- read-only Listing-API
- Post-Detail und Kommentare
- Cursor-Pagination
- autorisierte Write-Endpunkte

## V1 Should-Haves

- BYO OIDC Provider
- verifizierte Moderator-Provider
- Community-Typen public/restricted/private
- Flairs
- Wiki
- weitere Posttypen
- Popular und News Feed
- Suche mit Operatoren
- Moderations-API
- Crowd Control, Harassment, Reputation und Ban-Evasion Module
- Follow User
- Hotkeys
- Dark Mode
- Accessibility-Polish

## Leitplanken fuer den Implementierungsplan

- zuerst Auth und pseudonyme Identitaet
- dann Communities, Posts, Kommentare und Votes
- danach Moderation und Agent-Service-Accounts
- dann API-Erweiterung und fortgeschrittene Discovery

## Architekturannahmen fuer den naechsten Schritt

- monolithischer Web-Start ist bevorzugt
- serverseitiges HTML ist Default
- HTMX deckt die interaktiven Teilupdates ab
- Agentenmoderation wird als Produktflaeche gebaut, nicht nur als Hintergrundjob
