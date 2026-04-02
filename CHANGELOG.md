# Changelog

All notable changes to this project are documented in this file.

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
