# Phase 07 Polish And Scale Prep

## Ziel

Agora wird von einem MVP zu einer robusteren V1 ausgebaut:

- Dark Mode und Tastaturkürzel
- Follow- und Block-Flows
- Community-Wiki
- Crossposts und Polls
- Produktions- und Performance-Vorbereitung

## Scope

### UX

- Cookie-basierter Theme-Toggle
- Desktop-Shortcuts fuer Suche, Feed-Navigation und Voting

### Social Graph

- Follow oder Unfollow von Accounts
- Block oder Unblock mit Hide-Verhalten fuer Feed und Profil

### Community Features

- Wiki-Seiten mit Edit-Flow fuer Mods
- Crossposts mit Quellattribution
- Poll-Posts mit Optionen und Voting

### Operations

- Produktions-Compose mit gemeinsamem Postgres-Netzwerk
- Nginx-Proxy fuer Static, Media und Gunicorn
- Sicherheitsrelevante Prod-Settings

## Akzeptanzkriterien

- Nutzer koennen zwischen Light und Dark Mode wechseln
- gefolgte Accounts beeinflussen den Home-Feed
- geblockte Accounts werden in Profil und Feed unterdrueckt
- Communities koennen Wiki-Seiten pflegen
- Crossposts und Polls funktionieren end-to-end
- eine nachvollziehbare Produktionskonfiguration liegt im Repo vor
