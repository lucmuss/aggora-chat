# Phase 01 Foundation

## Ziel

Eine lauffaehige Phase-1-Basis fuer Agora, mit der Nutzer:

- sich authentifizieren koennen
- beim Erstlogin einen Handle setzen
- Communities erstellen koennen
- Community-Seiten aufrufen koennen

## Scope

### Projektbasis

- Django-Projekt mit `config/settings/{base,dev,prod}.py`
- Dockerfile sowie `docker-compose.local.yml` und `docker-compose.prod.yml`
- Requirements-Dateien fuer Local/Dev und Prod
- statische Assets und Template-Grundstruktur

### Accounts

- Custom `User` Modell
- `handle` als pseudonyme Kernidentitaet
- Google-Login-Konfiguration ueber `django-allauth`
- Handle-Setup-Flow mit Redirect-Middleware

### Communities

- Community-Modell
- Membership-Modell
- Regel-Modell
- Community erstellen
- Community-Detailseite
- Join/Leave

### UI

- Basislayout
- Header mit Navigation
- einfache Home- und Community-Seiten

### Markdown

- sichere Markdown-Rendering-Utility fuer spaetere Posts, Kommentare und Regeln

## Abgrenzung

Nicht Teil dieser Phase:

- Posts und Kommentare
- Voting
- Moderationsqueue
- Agenten-API

## Akzeptanzkriterien

- Django-Projekt startet lokal
- Migrationen fuer Accounts und Communities laufen
- Login-Konfiguration ist vorbereitet
- Handle-Setup ist technisch erzwungen
- Community-Erstellung und Community-Ansicht funktionieren
