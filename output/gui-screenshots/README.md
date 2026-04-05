# GUI Screenshots

This directory is intentionally left without committed PNGs when the previously stored screenshots are stale, misleading, or captured from an outdated UI state.

If you need fresh screenshots, regenerate them with:

```bash
uv run python scripts/generate_screenshots.py
```

The generator writes desktop and mobile captures for the configured routes into this directory.

For live verification after deploys, capture the canonical production host when possible:

- `https://aggora.org`
