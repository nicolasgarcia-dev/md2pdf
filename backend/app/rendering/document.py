"""Assemble the standalone HTML document that both PDF renderers consume."""

from __future__ import annotations

import html
from dataclasses import dataclass

from .markdown import PYGMENTS_CSS, Rendered
from .themes import get_stylesheet


@dataclass(frozen=True)
class BuildOptions:
    theme: str
    title: str
    include_toc: bool
    enable_math: bool
    enable_mermaid: bool


_KATEX_CSS_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
_KATEX_JS_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"
_KATEX_AUTO_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
_MERMAID_JS_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11.4.0/dist/mermaid.min.js"


def build_html(rendered: Rendered, options: BuildOptions) -> str:
    """Assemble a full HTML document for PDF rendering.

    The document is self-contained: CSS is inlined, and the only external
    references are KaTeX / Mermaid assets, which are only added when the
    source document needs them. WeasyPrint is never given documents that
    require those scripts (see ``dispatcher``).
    """
    head: list[str] = [
        '<meta charset="utf-8">',
        f"<title>{html.escape(options.title)}</title>",
        f"<style>{get_stylesheet(options.theme)}</style>",
        f"<style>{PYGMENTS_CSS}</style>",
    ]

    if options.enable_math:
        head.append(f'<link rel="stylesheet" href="{_KATEX_CSS_CDN}">')

    body_parts: list[str] = []
    if options.include_toc and rendered.toc_html:
        body_parts.append(rendered.toc_html)
    body_parts.append(f'<main class="document">{rendered.html_body}</main>')

    scripts: list[str] = []
    if options.enable_math:
        scripts.append(f'<script defer src="{_KATEX_JS_CDN}"></script>')
        scripts.append(f'<script defer src="{_KATEX_AUTO_CDN}"></script>')
        scripts.append(
            "<script>document.addEventListener('DOMContentLoaded',function(){"
            "renderMathInElement(document.body,{delimiters:["
            "{left:'$$',right:'$$',display:true},"
            "{left:'$',right:'$',display:false}"
            "],throwOnError:false});"
            "window.__mathReady=true;});</script>"
        )
    if options.enable_mermaid:
        scripts.append(f'<script type="module">'
                       f"import mermaid from '{_MERMAID_JS_CDN.replace('.min.js','.esm.min.mjs')}';"
                       "mermaid.initialize({startOnLoad:false,securityLevel:'strict'});"
                       "(async()=>{await mermaid.run({querySelector:'pre.mermaid'});"
                       "window.__mermaidReady=true;})();"
                       "</script>")

    return (
        "<!doctype html><html lang='en'><head>"
        + "".join(head)
        + "</head><body>"
        + "".join(body_parts)
        + "".join(scripts)
        + "</body></html>"
    )
