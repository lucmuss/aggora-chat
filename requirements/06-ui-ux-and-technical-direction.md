# UI UX And Technical Direction

## Produktanmutung

Die Plattform soll Reddit-aehnlich wirken, ohne ein Pixel-Klon zu sein.

## Informationsarchitektur

### Kernrouten

- `/`
- `/c/<community-slug>/`
- `/c/<community-slug>/post/<id>/<slug>/`
- `/u/<handle>/`
- `/mod/<community-slug>/...`

### Grundlayout

- Header mit Logo, Suche, Create und User Menu
- Feed-Spalte plus Sidebar
- responsive auf Desktop und Mobile

## Interaktionsmuster

- kompakte Post-Listings
- sichtbare Meta-Zeile mit Community, Autor, Zeit, Score und Kommentaranzahl
- dominante Vote-UI
- Post-Detail mit Kommentarbaum
- Mod-Workspace mit Queue, Log und Appeals

## Community-Elemente

- Banner und Icon
- Join/Leave
- sichtbare Regeln
- Flairs
- optional Wiki/Long-Form-Doku

## Technische Richtung

- Django als Web-Framework
- HTMX fuer partielle Interaktionen
- Tailwind fuer konsistente UI-Bausteine
- serverseitig gerenderte Seiten als Default

## HTMX-Kandidaten

- Votes
- Save/Unsave
- Kommentar erstellen
- Moderationsaktionen
- Queue-Filter

## Performance

### MVP

- Feed-Caching pro Community und Sortierung
- schnelle Teilupdates fuer Interaktionen
- performante Rendering-Strategie fuer Kommentarbaeume

## V1

- Hotkeys fuer Desktop
- Dark Mode
- Accessibility-Basics

## Akzeptanzkriterien

- Kernseiten sind schnell und konsistent
- Vote- und Moderationsaktionen fuehlen sich direkt an
- UI ist klar, dicht und fuer Diskussionen optimiert
