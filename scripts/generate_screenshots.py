import asyncio
import os

from playwright.async_api import async_playwright

BASE_URL = os.environ.get("BASE_URL", "https://aggora.kolibri-kollektiv.eu")
OUTPUT_DIR = "output/gui-screenshots"

ROUTES = [
    {"name": "00-landing-page", "url": "/"},
    {"name": "01-login", "url": "/accounts/login/"},
    {"name": "02-signup", "url": "/accounts/signup/"},
    {"name": "03-popular", "url": "/popular/"},
    {"name": "04-communities", "url": "/c/"},
    {"name": "05-freya-lounge", "url": "/c/freya-seed-lounge/"},
    {"name": "06-search", "url": "/search/"},
]

VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "mobile", "width": 390, "height": 844},
]

async def capture_screenshots():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        for viewport in VIEWPORTS:
            context = await browser.new_context(
                viewport={"width": viewport["width"], "height": viewport["height"]},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15" if viewport["name"] == "mobile" else None
            )
            page = await context.new_page()

            for route in ROUTES:
                filename = f"{OUTPUT_DIR}/{route['name']}-{viewport['name']}.png"
                print(f"Taking screenshot: {route['url']} ({viewport['name']}) -> {filename}")
                await page.goto(f"{BASE_URL}{route['url']}")
                # Kurze Pause für Animationen / HTMX load
                await page.wait_for_timeout(1000)
                await page.screenshot(path=filename, full_page=True)

            await context.close()

        await browser.close()

if __name__ == "__main__":
    print(f"Starting screenshot generation to {OUTPUT_DIR}...")
    asyncio.run(capture_screenshots())
    print("All screenshots generated successfully!")
