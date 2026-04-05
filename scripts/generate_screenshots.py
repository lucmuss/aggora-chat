import asyncio
import os
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

BASE_URL = os.environ.get("BASE_URL", "https://aggora.kolibri-kollektiv.eu").rstrip("/")
OUTPUT_DIR = "output/gui-screenshots"
LOGIN_EMAIL = os.environ.get("SCREENSHOT_LOGIN_EMAIL", "ariane.keller01@mailseed.test")
LOGIN_PASSWORD = os.environ.get("SCREENSHOT_LOGIN_PASSWORD", "SeedPass!2026")

PUBLIC_ROUTES = [
    {"name": "00-home", "url": "/"},
    {"name": "01-popular", "url": "/popular/"},
    {"name": "02-communities", "url": "/c/"},
    {"name": "03-community-detail", "url": "/c/freya-seed-lounge/"},
    {"name": "04-community-landing", "url": "/c/freya-seed-lounge/landing/"},
    {"name": "05-search", "url": "/search/?q=design"},
    {"name": "06-login", "url": "/accounts/login/"},
    {"name": "07-signup", "url": "/accounts/signup/"},
    {"name": "08-password-reset", "url": "/accounts/password/reset/"},
]

AUTH_ROUTES = [
    {"name": "20-home-auth", "url": "/"},
    {"name": "21-notifications", "url": "/accounts/notifications/"},
    {"name": "22-referrals", "url": "/accounts/referrals/"},
    {"name": "23-settings", "url": "/accounts/settings/"},
    {"name": "24-onboarding", "url": "/accounts/get-started/"},
    {"name": "25-profile-posts", "url": "/u/ariane_keller/"},
    {"name": "26-profile-saved", "url": "/u/ariane_keller/?tab=saved"},
    {"name": "27-community-create", "url": "/c/create/"},
    {"name": "28-community-submit", "url": "/c/freya-seed-lounge/submit/"},
    {"name": "29-mfa-setup", "url": "/accounts/mfa/"},
]

VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900, "is_mobile": False},
    {"name": "mobile", "width": 390, "height": 844, "is_mobile": True},
]


async def wait_for_stable_page(page):
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(1200)


async def capture(page, name, viewport_name):
    filename = f"{OUTPUT_DIR}/{name}-{viewport_name}.png"
    print(f"Taking screenshot -> {filename}")
    await page.screenshot(path=filename, full_page=True)


async def goto_and_capture(page, route, viewport_name):
    print(f"Opening {route['url']} ({viewport_name})")
    await page.goto(f"{BASE_URL}{route['url']}", wait_until="domcontentloaded")
    await wait_for_stable_page(page)
    await capture(page, route["name"], viewport_name)


async def login(page):
    print("Logging in with seeded account")
    await page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded")
    await wait_for_stable_page(page)
    await page.locator("#id_login").fill(LOGIN_EMAIL)
    await page.locator("#id_password").fill(LOGIN_PASSWORD)
    await page.locator("form.login button[type='submit']").click()
    await wait_for_stable_page(page)


async def capture_dynamic_authenticated_routes(page, viewport_name):
    print("Discovering dynamic authenticated pages")

    await page.goto(f"{BASE_URL}/c/freya-seed-lounge/", wait_until="domcontentloaded")
    await wait_for_stable_page(page)

    post_link = page.locator("a[href*='/post/']").first
    if await post_link.count():
        post_href = await post_link.get_attribute("href")
        if post_href:
            await page.goto(urljoin(BASE_URL, post_href), wait_until="domcontentloaded")
            await wait_for_stable_page(page)
            await capture(page, "30-post-detail", viewport_name)

    landing_link = page.locator("a[href$='/landing/']").first
    if await landing_link.count():
        landing_href = await landing_link.get_attribute("href")
        if landing_href:
            await page.goto(urljoin(BASE_URL, landing_href), wait_until="domcontentloaded")
            await wait_for_stable_page(page)
            await capture(page, "31-community-landing-auth", viewport_name)


async def capture_viewport(playwright, viewport):
    browser = await playwright.chromium.launch()
    context = await browser.new_context(
        viewport={"width": viewport["width"], "height": viewport["height"]},
        is_mobile=viewport["is_mobile"],
        has_touch=viewport["is_mobile"],
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
            if viewport["is_mobile"]
            else None
        ),
    )
    page = await context.new_page()

    for route in PUBLIC_ROUTES:
        await goto_and_capture(page, route, viewport["name"])

    await login(page)
    for route in AUTH_ROUTES:
        await goto_and_capture(page, route, viewport["name"])
    await capture_dynamic_authenticated_routes(page, viewport["name"])

    await context.close()
    await browser.close()


async def capture_screenshots():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    async with async_playwright() as playwright:
        for viewport in VIEWPORTS:
            await capture_viewport(playwright, viewport)


if __name__ == "__main__":
    print(f"Starting screenshot generation to {OUTPUT_DIR} from {BASE_URL}...")
    asyncio.run(capture_screenshots())
    print("All screenshots generated successfully!")
