# Changelog

All notable changes to this project are documented in this file.

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
