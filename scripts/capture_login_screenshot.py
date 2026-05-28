#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temporary script: visit login page and capture screenshot using Playwright directly.
"""
import asyncio
import os

# Use backend venv if available
venv_python = os.path.join(
    os.path.dirname(__file__), "..", "backend", "venv", "bin", "python"
)
if os.path.exists(venv_python):
    # Script will be run with system python3 - ensure we use venv's playwright
    pass


async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Error: Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    url = "http://localhost:81/login"
    output_path = "/code/sec-toolkit/data/login_screenshot.png"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"Navigating to: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            if response:
                print(f"  Status: {response.status}")
            print(f"  URL: {page.url}")
            print(f"  Title: {page.title()}")

            # Wait for form
            try:
                await page.wait_for_selector("form", timeout=5000)
                print("  Login form: present")
            except Exception:
                print("  Login form: not found (page may still be loading)")

            # Detect theme
            theme = await page.evaluate(
                """() => {
                const el = document.documentElement;
                if (el.classList.contains('dark')) return 'dark';
                if (el.classList.contains('light')) return 'light';
                return 'unknown';
            }"""
            )
            print(f"  Theme: {theme}")

            await page.wait_for_timeout(1500)

            await page.screenshot(path=output_path, full_page=True)
            print(f"  Screenshot saved: {output_path}")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
