"""Built-in document themes.

Each theme is a pair of CSS stylesheets loaded in order: ``base.css`` which
defines the page geometry, typography resets, code blocks, math alignment,
tables and TOC, and a per-theme stylesheet that layers visual identity on
top. Stylesheets are inlined into the rendered HTML so both renderers
produce identical output without any external fetches.
"""

from __future__ import annotations

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
]

_SLUGS = {t.slug for t in THEMES}


def is_valid(slug: str) -> bool:
    return slug in _SLUGS


@lru_cache(maxsize=32)
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def get_stylesheet(slug: str) -> str:
    """Return the concatenated CSS for a theme."""
    if not is_valid(slug):
        slug = "github"
    base = _read(_THEMES_DIR / "base.css")
    theme = _read(_THEMES_DIR / f"{slug}.css")
    return f"{base}\n{theme}"
