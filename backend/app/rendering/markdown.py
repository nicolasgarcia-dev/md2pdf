"""Markdown -> HTML pipeline.

The pipeline preserves raw LaTeX math and Mermaid fences as-is so that the
downstream PDF renderer can decide how to handle them. WeasyPrint does not
execute JavaScript, therefore documents containing math or diagrams are
routed to the Chromium renderer by ``analyze``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound


_PYGMENTS_FORMATTER = HtmlFormatter(nowrap=False, cssclass="codehilite")

# Pygments stylesheet, inlined into the document head so WeasyPrint and
# Chromium produce identical output without an extra HTTP round trip.
PYGMENTS_CSS: str = _PYGMENTS_FORMATTER.get_style_defs(".codehilite")


def _highlight(code: str, name: str, _attrs: object) -> str:
    lang = (name or "").strip().lower()
    if lang == "mermaid":
        # Preserve the original source so the renderer can run Mermaid later.
        return f'<pre class="mermaid">{html.escape(code)}</pre>'
    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(code)
    except ClassNotFound:
        return ""  # Fall back to markdown-it default rendering.
    return highlight(code, lexer, _PYGMENTS_FORMATTER)


def _build_parser() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True, "highlight": _highlight})
        .enable(["table", "strikethrough"])
        .use(anchors_plugin, min_level=1, max_level=4, permalink=False, slug_func=_slugify)
        .use(footnote_plugin)
        .use(tasklists_plugin, enabled=True)
        .use(dollarmath_plugin, allow_space=True, allow_digits=True, double_inline=False)
    )
    return md


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text or "section"


_parser = _build_parser()


@dataclass
class RenderAnalysis:
    has_math: bool
    has_mermaid: bool
    has_images: bool

    @property
    def needs_chromium(self) -> bool:
        # Math is rendered fine by WeasyPrint only if pre-rendered to HTML.
        # We render it client-side with KaTeX inside Chromium, so any math
        # in the document forces the Chromium path.
        return self.has_math or self.has_mermaid


_MATH_INLINE_RE = re.compile(r"(?<!\\)\$[^\$\n]+?\$")
_MATH_DISPLAY_RE = re.compile(r"(?<!\\)\$\$.+?\$\$", re.DOTALL)
_MERMAID_RE = re.compile(r"^```mermaid\b", re.MULTILINE)


def analyze(markdown: str) -> RenderAnalysis:
    return RenderAnalysis(
        has_math=bool(_MATH_INLINE_RE.search(markdown) or _MATH_DISPLAY_RE.search(markdown)),
        has_mermaid=bool(_MERMAID_RE.search(markdown)),
        has_images="![" in markdown,
    )


@dataclass
class Rendered:
    html_body: str
    toc_html: str
    analysis: RenderAnalysis


def render_markdown(markdown: str) -> Rendered:
    analysis = analyze(markdown)
    body = _parser.render(markdown)
    toc = _build_toc(markdown)
    return Rendered(html_body=body, toc_html=toc, analysis=analysis)


_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)


def _build_toc(markdown: str) -> str:
    headings: list[tuple[int, str, str]] = []
    in_fence = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        text = m.group(2).strip()
        headings.append((level, text, _slugify(text)))

    if not headings:
        return ""

    parts: list[str] = ['<nav class="toc" aria-label="Table of contents"><h2>Contents</h2><ul>']
    current = 1
    for level, text, slug in headings:
        while current < level:
            parts.append("<ul>")
            current += 1
        while current > level:
            parts.append("</ul>")
            current -= 1
        parts.append(f'<li><a href="#{html.escape(slug)}">{html.escape(text)}</a></li>')
    while current > 1:
        parts.append("</ul>")
        current -= 1
    parts.append("</ul></nav>")
    return "".join(parts)
