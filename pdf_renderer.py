"""
pdf_renderer.py
Renders HTML to PDF bytes using a persistent Playwright Chromium instance.
A single browser is reused across requests to avoid cold-start overhead.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level singletons
_playwright = None
_browser = None
_lock = asyncio.Lock()


async def get_browser():
    """Return a running Chromium browser, launching one if needed."""
    global _playwright, _browser

    async with _lock:
        if _browser is not None and _browser.is_connected():
            return _browser

        # Import here so the module loads even if playwright isn't installed yet
        from playwright.async_api import async_playwright

        logger.info("[PDF] Launching Chromium…")
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        logger.info("[PDF] Chromium ready")
        return _browser


async def render_pdf(html: str, landscape: bool = False) -> bytes:
    """Render an HTML string to A4 PDF bytes."""
    browser = await get_browser()
    page = await browser.new_page()
    try:
        await page.set_content(html, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            landscape=landscape,
            print_background=True,
            margin={
                "top": "0mm",
                "bottom": "0mm",
                "left": "0mm",
                "right": "0mm",
            },
        )
        return pdf_bytes
    finally:
        await page.close()
