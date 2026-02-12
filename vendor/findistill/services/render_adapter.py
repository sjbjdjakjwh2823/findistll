import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def render_html_to_text_async(html_bytes: bytes, base_url: Optional[str] = None) -> str:
    """
    Render HTML with Playwright (Chromium) and return visible text.
    """
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        logger.warning(f"Playwright not available: {e}")
        return html_bytes.decode(errors="ignore")

    html_str = html_bytes.decode(errors="ignore")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            if base_url:
                await page.goto(base_url)
            await page.set_content(html_str, wait_until="networkidle")
            text = await page.inner_text("body")
            await browser.close()
            return text or ""
    except Exception as e:
        logger.warning(f"Playwright render failed: {e}")
        return html_str


async def render_html_to_html_async(html_bytes: bytes, base_url: Optional[str] = None) -> str:
    """Render HTML with Playwright and return full DOM HTML."""
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        logger.warning(f"Playwright not available: {e}")
        return html_bytes.decode(errors="ignore")

    html_str = html_bytes.decode(errors="ignore")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            if base_url:
                await page.goto(base_url)
            await page.set_content(html_str, wait_until="networkidle")
            dom = await page.content()
            await browser.close()
            return dom or html_str
    except Exception as e:
        logger.warning(f"Playwright render failed: {e}")
        return html_str
