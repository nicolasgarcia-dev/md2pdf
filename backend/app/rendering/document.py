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


# Repaint every CSS `background-image: url("data:image/svg+xml,...")` as a
# high-resolution PNG via canvas, then patch the rule with `background-size`
# set to the SVG's natural size so the visual tiling stays identical. Chrome's
# PDF generation rasterizes background SVGs at ~CSS-pixel resolution (≈96 DPI),
# but it embeds PNGs at their native pixel count — so swapping in an 8×-larger
# PNG buys roughly an 8× sharper background in print without any change to
# Mermaid or KaTeX (those use inline <svg> / HTML, not CSS backgrounds).
_SVG_BG_UPRES_JS = """
(() => {
  const run = async () => {
  const SCALE = 8;
  const SVG_RE = /url\\(\\s*(?:"(data:image\\/svg\\+xml[^"]*)"|'(data:image\\/svg\\+xml[^']*)'|(data:image\\/svg\\+xml[^)\\s]*))\\s*\\)/i;

  function rasterize(svgUri) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const w = img.naturalWidth || 40;
        const h = img.naturalHeight || 40;
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(w * SCALE);
        canvas.height = Math.round(h * SCALE);
        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        try { resolve({ png: canvas.toDataURL('image/png'), w, h }); }
        catch (_) { resolve(null); }
      };
      img.onerror = () => resolve(null);
      img.src = svgUri;
    });
  }

  const cache = new Map();
  async function get(uri) {
    if (!cache.has(uri)) cache.set(uri, await rasterize(uri));
    return cache.get(uri);
  }

  async function patchRule(rule) {
    if (!rule.style) return;
    const bg = rule.style.backgroundImage || '';
    if (!bg.includes('data:image/svg+xml')) return;
    const m = bg.match(SVG_RE);
    if (!m) return;
    const uri = m[1] || m[2] || m[3];
    const r = await get(uri);
    if (!r) return;
    try {
      rule.style.backgroundImage = `url("${r.png}")`;
      // Preserve original tile dimensions so a 40×40 pattern stays a 40×40
      // pattern visually — only the source bitmap is denser.
      rule.style.backgroundSize = `${r.w}px ${r.h}px`;
    } catch (_) {}
  }

  async function walk(rules) {
    for (const rule of rules) {
      await patchRule(rule);
      if (rule.cssRules) await walk(rule.cssRules);
    }
  }

  try {
    for (const sheet of document.styleSheets) {
      try { await walk(sheet.cssRules || []); } catch (_) {}
    }
  } finally {
    window.__svgBgsReady = true;
  }
  };
  if (document.readyState === 'complete') run();
  else window.addEventListener('load', run, { once: true });
})();
"""


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

    scripts: list[str] = [f"<script>{_SVG_BG_UPRES_JS}</script>"]
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
                       "const computedFont = window.getComputedStyle(document.body).fontFamily;"
                       "mermaid.initialize({"
                       "  startOnLoad: false,"
                       "  securityLevel: 'strict',"
                       "  theme: 'base',"
                       "  themeVariables: { fontFamily: computedFont }"
                       "});"
                       "(async()=>{"
                       "  try {"
                       "    await mermaid.run({querySelector:'pre.mermaid'});"
                       "  } catch(_){}"
                       "  window.__mermaidReady=true;"
                       "})();"
                       "</script>")

    return (
        "<!doctype html><html lang='en'><head>"
        + "".join(head)
        + "</head><body>"
        + "".join(body_parts)
        + "".join(scripts)
        + "</body></html>"
    )
