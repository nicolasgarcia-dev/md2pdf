"""Built-in document themes.

Each theme is a pair of CSS stylesheets loaded in order: ``base.css`` which
defines the page geometry, typography resets, code blocks, math alignment,
tables and TOC, and a per-theme stylesheet that layers visual identity on
top. Stylesheets are inlined into the rendered HTML so both renderers
produce identical output without any external fetches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_THEMES_DIR = _ASSETS / "themes"


@dataclass(frozen=True)
class Theme:
    slug: str
    name: str
    description: str


THEMES: list[Theme] = [
    Theme("github", "GitHub", "Clean, familiar sans-serif look similar to GitHub's README rendering."),
    Theme("academic", "Academic", "Serif body, justified paragraphs and numbered headings. Suitable for papers."),
    Theme("minimal", "Minimal", "Low-contrast, generous whitespace, understated typography."),
    Theme("elegant", "Elegant", "Warm serif body with contrasting sans-serif headings."),
    Theme("modern", "Modern", "Tight sans-serif, accent color on headings and links."),
    Theme("custom", "Custom CSS", "Write your own CSS in the editor that appears below the toolbar."),
]

_SLUGS = {t.slug for t in THEMES}


def is_valid(slug: str) -> bool:
    return slug in _SLUGS


@lru_cache(maxsize=32)
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _inject_page_background(custom_css: str) -> str:
    """Auto-add @page background-color matching body/html background.

    This ensures the full page (content area + margin gutters) gets the same
    color so there is no visible boundary between the margin and content area.
    Skipped when the user has already written an @page rule with a background.
    """
    if re.search(r"@page\s*\{[^}]*background", custom_css, re.DOTALL):
        return custom_css
    m = re.search(
        r"(?:html\s*,\s*body|body\s*,\s*html|html|body)\s*\{([^}]*)\}",
        custom_css,
        re.DOTALL,
    )
    if m:
        bg = re.search(r"background(?:-color)?\s*:\s*([^;}\n]+)", m.group(1))
        if bg:
            color = bg.group(1).strip()
            return f"@page {{ background-color: {color}; }}\n" + custom_css
    return custom_css


def get_stylesheet(slug: str, custom_css: str = "") -> str:
    """Return the concatenated CSS for a theme.

    When slug is 'custom', base.css is prepended to the caller-supplied CSS.
    """
    if slug == "custom":
        base = _read(_THEMES_DIR / "base.css")
        if custom_css.strip():
            patched = _inject_page_background(custom_css)
            return f"{base}\n{patched}"
        return base
    if not is_valid(slug):
        slug = "github"
    base = _read(_THEMES_DIR / "base.css")
    theme = _read(_THEMES_DIR / f"{slug}.css")
    return f"{base}\n{theme}"


def _scope_selector(selector: str) -> str:
    """Prefix each comma-part of a CSS selector with #preview."""
    parts = []
    for part in selector.split(","):
        part = part.strip()
        if not part:
            continue
        # Strip leading html keyword (e.g. "html, body" or "html body")
        normalized = re.sub(r"^html\s*,?\s*", "", part).strip()
        if normalized in ("body", ""):
            parts.append("#preview")
        elif normalized.startswith("body ") or normalized.startswith("body\t"):
            parts.append("#preview " + normalized[4:].strip())
        elif re.match(r"^main\.document\b", normalized):
            tail = normalized[len("main.document"):]
            parts.append("#preview" + tail if tail else "#preview")
        else:
            parts.append("#preview " + normalized)
    return ", ".join(parts)


def get_preview_stylesheet(slug: str, custom_css: str = "") -> str:
    """Return theme CSS scoped to #preview for the live preview pane.

    @page rules are removed (print-only) and all selectors are prefixed with
    #preview so the theme does not bleed into the editor or toolbar.
    """
    full_css = get_stylesheet(slug, custom_css)

    # Remove @page blocks (print geometry is irrelevant on screen)
    full_css = re.sub(r"@page\s*\{[^}]*\}", "", full_css, flags=re.DOTALL)

    result: list[str] = []
    i, n = 0, len(full_css)

    while i < n:
        # Skip whitespace and block comments
        while i < n and (full_css[i].isspace() or full_css[i:i+2] == "/*"):
            if full_css[i:i+2] == "/*":
                end = full_css.find("*/", i + 2)
                i = (end + 2) if end != -1 else n
            else:
                i += 1
        if i >= n:
            break

        # At-rule
        if full_css[i] == "@":
            start = i
            while i < n and full_css[i] not in "{;":
                i += 1
            if i >= n:
                break
            if full_css[i] == ";":
                result.append(full_css[start : i + 1])
                i += 1
            else:
                depth = 0
                while i < n:
                    if full_css[i] == "{":
                        depth += 1
                    elif full_css[i] == "}":
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    i += 1
                result.append(full_css[start:i])
            continue

        # Regular rule: read until opening brace
        sel_start = i
        while i < n and full_css[i] != "{":
            i += 1
        if i >= n:
            break
        selector = full_css[sel_start:i].strip()
        i += 1  # skip '{'

        decl_start = i
        while i < n and full_css[i] != "}":
            i += 1
        declarations = full_css[decl_start:i]
        if i < n:
            i += 1  # skip '}'

        if not selector:
            continue
        new_sel = _scope_selector(selector)
        if new_sel:
            result.append(f"{new_sel} {{{declarations}}}")

    # Restore preview container layout that body/html rules might override
    result.append("#preview { padding: 24px 28px !important; overflow: auto !important; }")
    return "\n".join(result)
