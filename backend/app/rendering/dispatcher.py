"""Render dispatcher.

Chromium is the primary engine because it produces the most faithful output
(GFM checkboxes, math, Mermaid, true content scaling). WeasyPrint is kept as
a fallback so the service stays available if Chromium fails to start or
render — for example, if the browser crashes or the host is missing the
shared libraries Playwright needs.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from .chromium import chromium
from .document import BuildOptions, build_html
from .markdown import render_markdown
from .weasy import render_pdf as weasy_render
from .themes import is_valid

logger = logging.getLogger("md2pdf")


@dataclass
class RenderResult:
    pdf: bytes
    engine: str  # "weasyprint" | "chromium"


SCALE_MIN = 0.6
SCALE_MAX = 1.4


def _clamp_scale(scale: float) -> float:
    if scale < SCALE_MIN:
        return SCALE_MIN
    if scale > SCALE_MAX:
        return SCALE_MAX
    return scale


async def render(
    markdown: str,
    *,
    theme: str = "github",
    title: str = "document",
    include_toc: bool = True,
    custom_css: str = "",
    scale: float = 1.0,
) -> RenderResult:
    if not is_valid(theme):
        theme = "github"
    scale = _clamp_scale(scale)
    rendered = render_markdown(markdown)

    options = BuildOptions(
        theme=theme,
        title=title,
        include_toc=include_toc,
        enable_math=rendered.analysis.has_math,
        enable_mermaid=rendered.analysis.has_mermaid,
        custom_css=custom_css,
    )
    html_document = build_html(rendered, options)

    # Primary path: Chromium for everything.
    try:
        await chromium.start()
        pdf = await chromium.render_pdf(
            html_document,
            wait_for_math=options.enable_math,
            wait_for_mermaid=options.enable_mermaid,
            scale=scale,
        )
        return RenderResult(pdf=pdf, engine="chromium")
    except Exception as exc:
        # Fallback to WeasyPrint to keep the service available.
        # WeasyPrint cannot honour `scale` faithfully (its `zoom` is not a
        # true content rescale), so the fallback PDF is rendered at 1.0.
        logger.warning("Chromium render failed, falling back to WeasyPrint: %s", exc)
        pdf = await asyncio.to_thread(weasy_render, html_document)
        return RenderResult(pdf=pdf, engine="weasyprint")
