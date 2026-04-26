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
    custom_css: str = ""


_KATEX_CSS_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
_KATEX_JS_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"
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
        f"<style>{PYGMENTS_CSS}</style>",
        f"<style>{get_stylesheet(options.theme, options.custom_css)}</style>",
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
        # dollarmath_plugin converts $...$ → <span class="math math-inline"> and
        # $$...$$ → <span class="math math-block">, so auto-render (which scans
        # for $ delimiters in text nodes) finds nothing. We target those spans
        # directly with katex.renderToString instead.
        # dollarmath_plugin (mdit-py-plugins) emits:
        #   inline $...$ → <span class="math inline">
        #   block  $$...$$ → <div class="math block">
        # Selectors: .math.inline and .math.block (two separate classes, no hyphen).
        scripts.append(
            "<script>document.addEventListener('DOMContentLoaded',function(){"
            "document.querySelectorAll('.math.inline').forEach(function(el){"
            "try{el.innerHTML=katex.renderToString(el.textContent.trim(),{displayMode:false,throwOnError:false});}catch(_){}"
            "});"
            "document.querySelectorAll('.math.block').forEach(function(el){"
            "try{el.innerHTML=katex.renderToString(el.textContent.trim(),{displayMode:true,throwOnError:false});}catch(_){}"
            "});"
            "window.__mathReady=true;});</script>"
        )
    if options.enable_mermaid:
        scripts.append(
            "<script>setTimeout(function(){window.__mermaidReady=true;},15000);</script>"
        )
        scripts.append(f'<script type="module">'
                       f"import mermaid from '{_MERMAID_JS_CDN.replace('.min.js','.esm.min.mjs')}';"
                       "mermaid.initialize({startOnLoad:false,securityLevel:'strict'});"
                       "(async()=>{try{await mermaid.run({querySelector:'pre.mermaid'});}catch(_){}"
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
