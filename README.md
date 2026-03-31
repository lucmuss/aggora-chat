# aggora-chat

Local Git repository for `aggora-chat`.

Target domain:

- `https://aggora.kolibri-kollektiv.eu`

## Environment configuration

Agora now follows the same configuration style as the Freya reference project:

- `.env.example` documents the supported runtime variables
- `.env` is loaded automatically by Django settings
- `DATABASE_URL` is supported for external Postgres setups
- explicit fallback variables still work for local Compose workflows
- app branding, support links, mail, cache, search, and security flags are environment-driven

Copy `.env.example` to `.env` and adjust the values for your environment.
