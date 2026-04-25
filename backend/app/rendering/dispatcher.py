"""Pick the lightest renderer that produces a faithful PDF."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .chromium import chromium
from .document import BuildOptions, build_html
from .markdown import render_markdown
from .weasy import render_pdf as weasy_render
from .themes import is_valid


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
    force_high_fidelity: bool = False,
    custom_css: str = "",
    scale: float = 1.0,
) -> RenderResult:
    if not is_valid(theme):
        theme = "github"
    scale = _clamp_scale(scale)
    rendered = render_markdown(markdown)
    # Any non-default scale is routed through Chromium: WeasyPrint's `zoom`
    # is a viewport hint rather than a true content rescale, and Chromium
    # also handles GFM checkboxes and other elements with higher fidelity.
    scale_changed = abs(scale - 1.0) > 1e-6
    needs_chromium = force_high_fidelity or rendered.analysis.needs_chromium or scale_changed

    options = BuildOptions(
        theme=theme,
        title=title,
        include_toc=include_toc,
        enable_math=rendered.analysis.has_math,
        enable_mermaid=rendered.analysis.has_mermaid,
        custom_css=custom_css,
    )
    html_document = build_html(rendered, options)

    if needs_chromium:
        await chromium.start()
        pdf = await chromium.render_pdf(
            html_document,
            wait_for_math=options.enable_math,
            wait_for_mermaid=options.enable_mermaid,
            scale=scale,
        )
        return RenderResult(pdf=pdf, engine="chromium")

    # WeasyPrint is blocking; run in a thread to avoid stalling the event loop.
    # Scale is always 1.0 here (non-default scale is routed through Chromium).
    pdf = await asyncio.to_thread(weasy_render, html_document)
    return RenderResult(pdf=pdf, engine="weasyprint")
