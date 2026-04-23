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


async def render(
    markdown: str,
    *,
    theme: str = "github",
    title: str = "document",
    include_toc: bool = True,
    force_high_fidelity: bool = False,
) -> RenderResult:
    if not is_valid(theme):
        theme = "github"
    rendered = render_markdown(markdown)
    needs_chromium = force_high_fidelity or rendered.analysis.needs_chromium

    options = BuildOptions(
        theme=theme,
        title=title,
        include_toc=include_toc,
        enable_math=rendered.analysis.has_math,
        enable_mermaid=rendered.analysis.has_mermaid,
    )
    html_document = build_html(rendered, options)

    if needs_chromium:
        await chromium.start()
        pdf = await chromium.render_pdf(
            html_document,
            wait_for_math=options.enable_math,
            wait_for_mermaid=options.enable_mermaid,
        )
        return RenderResult(pdf=pdf, engine="chromium")

    # WeasyPrint is blocking; run in a thread to avoid stalling the event loop.
    pdf = await asyncio.to_thread(weasy_render, html_document)
    return RenderResult(pdf=pdf, engine="weasyprint")
