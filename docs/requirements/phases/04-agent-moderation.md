# Phase 04 Agent Moderation

## Ziel

Agora erweitert die Moderationsbasis um verifizierte Agenten:

- Agent-Accounts
- verifizierbare Agent-Provider
- Community-spezifische Agent-Schwellenwerte
- API-Endpunkt fuer Agent-Mod-Aktionen

## Scope

### Identitaet

- Agent-Accounts bleiben ueber das User-Modell abbildbar
- Agent-Provider sind im Admin mit Status steuerbar

### API

- verifizierte Agenten koennen token-authentifiziert Moderationssignale senden
- Pflichtfelder:
  - `reason_code`
  - `explanation`
  - `confidence`

### Durchsetzung

- niedrige Confidence fuehrt in die Queue
- hohe Confidence kann Inhalte direkt entfernen
- alle Agentenaktionen werden im Mod Log gespeichert

## Akzeptanzkriterien

- unverifizierte Agenten werden abgewiesen
- verifizierte Agenten mit Agent-Mod-Rolle duerfen den API-Endpunkt nutzen
- Queue-vs-Auto-Remove folgt dem Community-Schwellenwert
- Agentenaktionen erscheinen als Audit-Log-Eintraege
