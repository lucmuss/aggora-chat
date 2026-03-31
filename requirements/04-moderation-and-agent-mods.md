# Moderation And Agent Mods

## Rollenmodell

### Mindestrollen

- Plattform-Admin
- Community-Owner
- Community-Moderator
- Agent-Mod

## Moderationsoberflaeche

### MVP

- eigener Mod-Bereich pro Community
- Mod Queue mit mindestens einem startfaehigen Subset aus:
  - needs review
  - reported
  - removed
  - unmoderated
- Mod Actions:
  - approve
  - remove
  - mark as spam
  - ignore reports
- Ban/Unban
- Mod Log
- Removal Reasons
- einfache Mod Mail fuer Appeals und Anfragen

## Reports

### MVP

- Nutzer koennen Posts und Kommentare melden
- Report besteht aus:
  - Reason
  - optionalem Freitext
- Reports erzeugen Queue-Eintraege

## Agentenmoderation

### Grundmodell

Agenten werden wie Mod-Accounts behandelt, aber mit haerteren Kontrollmechanismen:

- verifizierte technische Identitaet
- eingeschraenkte Permissions
- verpflichtender Audit Trail
- klare Community- und Plattform-Policy-Bindung

### MVP

- Agenten als Service Accounts
- verifizierbar ueber Admin-Prozess
- API-Zugriff mit Scopes
- pro Community konfigurierbare Aktionstypen:
  - flag for review
  - auto-remove
  - warn
  - rate-limit
  - lock

### Policy Engine

- Plattform-Policies als globale Regeln
- Community-Policies als lokales Ruleset
- Schwellenwerte fuer:
  - Queue statt Autoaction
  - Autoaction bei hohem Vertrauen

### Erklaerungspflicht

Jede Agentenaktion muss erzeugen:

- Reason Code
- human-readable Erklaerung
- Referenz auf relevante Policy

## V1

- Crowd-Control-Modul
- Harassment-Filter
- Reputation-Filter
- Ban-Evasion-Signale
- getrennte Agenten-Pipelines mit eigenem Community-Schalter und Staerkegrad
- Moderator User Context Panel
- Reporter-Qualitaetslogik

## Harte Produktanforderungen

- Agenten duerfen nicht unkontrolliert ohne Audit handeln
- Queue-first ist Default
- finale, harte Enforcement-Aktionen muessen nachvollziehbar und anfechtbar sein

## Akzeptanzkriterien

- Mods sehen eine funktionierende Queue
- Agenten koennen Items mit Begruendung in die Queue schieben
- jede Agentenaktion erscheint im Mod Log
- betroffene Nutzer koennen ueber Mod Mail Einspruch einreichen
