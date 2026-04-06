# Changelog

All notable changes to this project are documented in this file.

## [0.3.9] - 2026-04-06

Patch release focused on richer profile settings, moderation/reporting, content awards, mentions, browser notifications, and production Google Places support on `aggora.org`.

### Added
- Browser notification delivery preferences with live in-browser notification polling for signed-in members.
- `@mentions` autocomplete across thread and comment composers, mention link rendering, and dedicated mention notifications.
- Profile enrichment for banner images, age, country, region, city, and safer 18+ content preferences.
- Reporting and monthly content awards across posts and comments, including moderation queue visibility and profile totals.

### Changed
- Account settings now use the configured Google Places API key on production for city autocomplete while keeping country/region selection robust.
- Signup, password reset, and HTMX auth flows now fail more gracefully and keep users in a cleaner navigation flow.
- Mobile and community UI surfaces received another polish pass around navigation, sharing, and thread actions.

### Fixed
- Prevented HTMX login redirects from rendering inside existing templates on protected actions.
- Fixed comment replies, comment voting, password reset lookup, and install-prompt persistence issues.
- Corrected live profile rendering for uploaded avatar/banner assets and improved validation around usernames and location fields.

### Verified
- `python3 -m compileall apps templates static`
- `uv run python manage.py check`
- `uv run pytest -q`

## [0.3.8] - 2026-04-05

Patch release focused on the `aggora.org` production cutover, Cloudflare Tunnel routing, and documentation consistency.

### Added
- A dedicated Cloudflare migration runbook for the new canonical production domain.

### Changed
- Production documentation now treats `https://aggora.org` as the canonical public host and keeps the former `aggora.kolibri-kollektiv.eu` address as a legacy migration domain.
- Stack defaults now include `aggora.org` and `www.aggora.org` in the host and CSRF allow-lists.

### Fixed
- Added canonical-host redirect middleware so `www.aggora.org` can collapse onto the apex domain once the new image is deployed.
- Updated test coverage for the new host-normalization behavior.

### Verified
- `python3 -m compileall apps config templates`
- `uv run pytest -q`

## [0.3.7] - 2026-04-05

Patch release focused on mobile navigation, mobile sharing, and more thumb-friendly feed interactions.

### Added
- A dedicated mobile bottom navigation bar for `Home`, `Popular`, `Communities`, and `Search`.
- A mobile-first share sheet with large actions for copy, native share, WhatsApp, Telegram, email, and X.
- Fresh Playwright screenshot coverage for public and authenticated flows in `output/gui-screenshots/`.

### Changed
- Mobile headers now hide lower-priority actions so the top bar stays readable and collision-free.
- Feed cards now reduce metadata on small screens and surface one clearer primary discussion action.
- Community and thread sharing surfaces now route mobile users through a clearer invite/share flow.
- Login and signup keep the stronger branded treatment introduced in the earlier UI polish pass.

### Fixed
- Improved mobile tap targets by promoting the shared button system to 48px-high actions on small screens.
- Prevented the install prompt from colliding with the new bottom navigation on mobile.

### Verified
- `python3 -m compileall templates static apps`
- `uv run pytest -q`

## [0.3.6] - 2026-04-05

Patch release focused on search-friendly HTML, structured data, and crawlable community and thread surfaces.

### Added
- Shared SEO helpers for canonical URLs, cleaned descriptions, and structured data generation.
- JSON-LD for feeds, community pages, profile pages, and discussion threads.

### Changed
- Base templates now expose canonical, robots, Open Graph, and Twitter metadata with safe defaults.
- Feed sort controls now use real links with HTMX enhancement so crawlers can discover `Hot`, `New`, `Top`, and `Rising` views.
- Community, post, profile, and search pages now set page-specific SEO titles and descriptions without changing the visible UI.

### Fixed
- Search pages now explicitly use `noindex,follow` to avoid low-value search-result indexing.
- Thread, feed, and community templates now expose clearer semantic sections and breadcrumb structure for crawlers.

### Verified
- `python3 -m compileall apps config templates static`
- `uv run python manage.py check`
- `uv run pytest -q`

## [0.3.5] - 2026-04-05

Patch release focused on UI resilience, feedback clarity, form polish, and refreshed branding.

### Added
- Live availability checks for community names and slugs during community creation.
- A new Agora wordmark logo in the top-left header.

### Changed
- Global flash messages now use clearer success, warning, and error styling.
- Account settings now group notification controls more clearly and explain avatar upload limits.
- MFA setup now explains when two-factor authentication is required before admin access.

### Fixed
- Empty comment submissions now stay on the thread with inline validation instead of falling into a broken error flow.
- Duplicate comment submits are now guarded when users click the submit action repeatedly.
- Post and comment delete flows now provide confirmation and clear success feedback.
- First-week onboarding actions now point to working destinations for thread discovery and challenges.
- The header branding now uses the provided Agora logo instead of the placeholder mark.

### Verified
- `python3 -m compileall apps config templates static`
- `uv run pytest -q`

## [0.3.4] - 2026-04-05

Patch release focused on UI polish and trust-building fixes across account, discovery, profile, and sharing surfaces.

### Fixed
- Hid the guest-only welcome card for authenticated users on the home feed.
- Corrected the community discovery count copy and improved sidebar card separation.
- Refined the 2FA setup screen with safer copy actions, clearer messaging, and cleaner code-entry fields.
- Improved profile tab emphasis, comment vote alignment, and share button consistency on post detail pages.

### Verified
- `python3 -m compileall apps config templates static`
- `uv run pytest -q`

## [0.3.3] - 2026-04-05

Release focused on product polish, growth loops, explainable personalization, and a richer writing experience.

### Added
- Global search tabs, HTMX live search, and a `Ctrl+K` command palette for faster navigation.
- First-week missions, richer referral surfaces, and stronger challenge participation and submission flows.
- Community starter kits, reader-queue saved states, improved mod mail states, and owner dashboards for community health.
- Explainable `For You` ranking signals with card-level context about why a thread appears in the feed.
- Native Share API support with copy feedback across posts and community share surfaces.
- Lightweight rich Markdown editing toolbar with live preview for posts, comments, bios, wiki pages, and mod mail.

### Changed
- Community landing pages now work as stronger acquisition pages with social proof, challenge galleries, and clearer invite/share CTAs.
- Community settings, moderation queue, notifications, and account surfaces now use more consistent, product-led microcopy and clearer empty states.
- Profile bios now render safely as Markdown instead of plain text.

### Fixed
- Wiki read and edit flows now enforce community privacy consistently, preventing private-community wiki leaks.
- Comment, post, and challenge-entry creation now share a more coherent writing and discovery flow.

### Verified
- `python3 -m compileall apps config templates static`
- `uv run pytest -q`

## [0.3.2] - 2026-04-05

Patch release focused on GitHub CI reliability and repo-wide lint cleanup.

### Changed
- GitHub Actions now installs dependencies via `uv venv` plus `uv pip install -r requirements/dev.txt`.
- The CI test job now runs `pytest` against the dedicated test settings instead of relying on the ambient management-command environment.
- The Bandit job now excludes repo test files and test-only settings to avoid false-positive failures in CI.
- Ruff configuration and repo code were cleaned up so the lint job passes consistently.

### Fixed
- Resolved the broken import in the legacy search tests that blocked full pytest collection.

### Verified
- `uv run ruff check .`
- `uv run bandit -q -r apps config scripts -x 'apps/*/test*.py,apps/*/tests.py,config/settings/test.py' -s B105`
- `uv run pytest -q`

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
