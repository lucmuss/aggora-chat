# Product Scope

## Produktbild

Agora ist eine Reddit-aehnliche Plattform fuer thematische Communities mit folgenden Kerneigenschaften:

- viele eigenstaendige Communities
- voting-getriebene Sichtbarkeit
- pseudonyme Identitaet statt Realnamenpflicht
- Moderation ueber Menschen plus verifizierte Agenten-Moderatoren

## Kernprinzipien

### Many-Communities Model

Die Plattform besteht aus vielen kleineren thematischen Communities mit eigener Kultur, eigenen Regeln und eigenem Moderationsteam.

### Votes als Systemsignal

Upvotes und Downvotes sind keine reine Reaktion, sondern beeinflussen:

- Ranking und Sichtbarkeit
- Wahrnehmung von Relevanz
- Reputation/Karma
- Anti-Abuse-Signale

### Pseudonymitaet als Default

Die primaere Nutzungsidentitaet ist ein Handle/Username. Externe Logins wie Google oder OIDC sind nur Authentifizierungswege, nicht die sichtbare Kernidentitaet.

### Zwei-Ebenen-Regelmodell

Moderation muss immer in zwei Policy-Schichten arbeiten:

- Plattform-Policies
- Community-Policies

## Produktziele

- Reddit-aehnliche Community-Erfahrung mit moderner, klar auditierbarer Architektur
- starke Moderationswerkzeuge fuer Menschen
- Agentenmoderation als produktisiertes, kontrolliertes Feature
- API-faehige Plattform fuer eigene und externe Clients

## Nichtziele fuer den MVP

- vollstaendige Reddit-Feature-Paritaet
- komplexe Monetarisierung
- Realname- oder Social-Graph-first-Erfahrung
- vollautomatische, unueberpruefbare Moderationsentscheidungen
