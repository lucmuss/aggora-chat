# Changelog

All notable changes to this project are documented in this file.

## [0.3.1] - 2026-04-05

Release focused on backend quality, regression protection, and release hardening.

### Added
- Direct pytest coverage for account models, forms, middleware, security helpers, and views.
- Direct pytest coverage for community models, forms, services, privacy flows, invite flows, and URLs.
- Direct pytest coverage for post models, forms, services, views, vote tasks, and vote endpoints.
- Direct pytest coverage for moderation services, moderation views, search backends, API serializers/views, feed caching, infrastructure helpers, admin surfaces, template tags, and workflow/security regressions.

### Changed
- API search now forwards `post_type` and `media` filters to the active discovery backend.

### Verified
- `uv run pytest -q`

## [0.3.0] - 2026-04-02

Production-readiness pass focused on security hardening, account settings, API/web parity, richer demo seeding, and operational stability.

### Added
- Account settings for profile visibility and notification preferences.
- Staff MFA setup flow with TOTP verification for sensitive moderation and admin routes.
- Rate limiting middleware for login, posting, voting, and social actions.
- PWA offline fallback page and install prompt handling.
- Extended JSON seed data for multiple communities, challenges, wiki pages, curated posts, votes, and saved items.
- CI workflow with lint/test, Bandit security scan, and optional Playwright smoke screenshots.

### Changed
- API search now returns posts, communities, and users to match the web experience more closely.
- Community and wiki editors now support live Markdown preview.
- Container startup now supports automatic migrate and richer seeding in development and stack/prod-style Compose flows.
- Demo environment and live container were refreshed to serve the current `0.3.0` release.

### Fixed
- Eliminated the remaining `makemigrations --check` drift by committing the pending accounts index rename migration.
- Reduced Django 6 deprecation noise by updating the vote check constraint and opting forms into HTTPS URL assumptions.
- Removed local test warnings about a missing `staticfiles` directory by ensuring the path exists during repo runs.

### Verified
- `python3 -m compileall apps config templates static scripts`
- `uv run pytest -q`
- `uv run python manage.py test --noinput`
- `uv run python manage.py makemigrations --check --dry-run`

## [0.2.0] - 2026-04-02

Expanded the initial release with web search improvements, PWA groundwork, richer social login support, and editor usability upgrades.

### Added
- Quick-match search results for communities and user profiles on the web search page.
- GitHub social sign-in configuration and login/signup CTAs alongside Google sign-in.
- PWA baseline with a web manifest, service worker shell caching, and app icon.
- Live Markdown preview for post creation and community creation flows.
- Regression coverage for manifest/service worker/preview endpoints and the new search and signup UI paths.

### Changed
- Documentation now covers GitHub auth and the lightweight PWA shell.
- Search UI now reflects that posts are the primary indexed content while community/profile matches are surfaced directly in the page.

### Verified
- `python3 -m compileall apps config templates static`
- `uv run python manage.py test --noinput`

## [0.1.0] - 2026-04-02

Initial public release of `aggora-chat`.

### Added
- Community growth features including invite links, onboarding, suggested communities, challenges, leaderboards, share flows, and public landing pages.
- JSON-based demo seeding with documented test accounts.
- Refreshed Playwright screenshots under `output/gui-screenshots/`.
- Expanded documentation for setup, environment, testing, architecture, API examples, and known gaps.

### Fixed
- Web post creation now persists `url`, `image`, `flair`, `is_spoiler`, and `is_nsfw`.
- Modmail thread creation now uses the correct `subject` field.
- Community privacy and participation rules are enforced consistently in the web app and API.
- Community post-type restrictions are validated server-side.
- Post detail pages now receive the correct `joined` state.
- Feed, profile, search, and community templates now render shared post-list partials correctly.
- Search UI no longer promises unsupported user/community search.

### Verified
- `python3 -m compileall apps config templates`
- `uv run python manage.py test --noinput`
