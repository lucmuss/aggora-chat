# Identity And Auth

## Produktanforderung

Agora ist pseudonym-first. Login und Identitaet sind getrennt:

- Login: ueber externe Provider
- sichtbare Identitaet: Handle/Username in Agora

## MVP

### Google Login

- Google Login via OpenID Connect
- Authorization Code Flow
- Sessions mit CSRF-Schutz, SameSite-Cookies und Logout

### Erstlogin-Flow

- neuer Nutzer wird nach erfolgreichem Login in einen Handle-Setup-Flow geleitet
- Handle muss eindeutig sein
- Realname aus dem Identity Provider darf nicht als primaeres Public Label erzwungen werden

### Account-Verknuepfungen

- Account-Seite fuer verknuepfte Identitaeten
- im MVP mindestens Anzeige von Google als verknuepfte Identitaet

## V1

### BYO Identity Provider

- Login ueber registrierte OpenID-Connect-Provider
- Provider Registry mit:
  - Issuer URL
  - Discovery
  - Client ID
  - Client Secret
  - erlaubte Scopes

### Moderator- und Agenten-Verifikation

- Admin-Dashboard zum Verifizieren von Moderatoren-Providern oder Agenten-Accounts
- Statusmodell:
  - pending
  - verified
  - disabled

## Sicherheitsanforderungen

- klare Trennung von Nutzer-Accounts und Agent-Service-Accounts
- verifizierte Agenten duerfen nur nach positiver Admin-Pruefung Moderationsrollen erhalten
- Audit Trail fuer jede Verifikationsentscheidung

## Akzeptanzkriterien

- Google-Login funktioniert end-to-end
- neue Nutzer erhalten Handle-Setup
- Handle ist die sichtbare Primaeridentitaet
- Admin kann Agenten-Provider oder Agenten-Account als verifiziert markieren
