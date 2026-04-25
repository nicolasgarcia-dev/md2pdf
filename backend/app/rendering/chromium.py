"""Playwright/Chromium renderer: used when JavaScript is required (math or Mermaid).

A single browser is kept alive for the application's lifetime. Each render
uses a short-lived context and page to isolate state between requests.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from playwright.async_api import Browser, async_playwright


class ChromiumRenderer:
    def __init__(self) -> None:
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._browser is not None:
            return
        async with self._lock:
            if self._browser is not None:
                return
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--font-render-hinting=none",
                ],
            )

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def render_pdf(self, html_document: str, *, wait_for_math: bool, wait_for_mermaid: bool, scale: float = 1.0) -> bytes:
        assert self._browser is not None, "ChromiumRenderer.start() must be called first"
        context = await self._browser.new_context()
        try:
            page = await context.new_page()
            await page.set_content(html_document, wait_until="networkidle", timeout=30000)
            # Wait for asynchronous rendering signals emitted by the document.
            if wait_for_math:
                await page.wait_for_function("window.__mathReady === true", timeout=15000)
            if wait_for_mermaid:
                try:
                    await page.wait_for_function("window.__mermaidReady === true", timeout=20000)
                except Exception:
                    pass  # mermaid CDN unreachable — render PDF without diagrams
            return await page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                scale=scale,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},  # @page margin in CSS handles spacing
            )
        finally:
            await context.close()


chromium = ChromiumRenderer()
