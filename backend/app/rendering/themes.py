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


def apply_continuous_fusion(css: str) -> str:
    """Preprocess CSS to implement 'Fusión Continua' (Continuous Fusion).

    1. Extract background declarations from html/body selectors.
    2. Clean/sanitize them:
       - Exclude background-attachment: fixed or any background-attachment properties.
       - Strip '!important' priority modifiers.
    3. Inject these clean properties into the @page rule.
    4. Force html/body to have an absolute transparent background.
    """
    # Selector pattern matching blocks like:
    # html, body { ... }
    # body { ... }
    # html { ... }
    # taking into account whitespace and linebreaks.
    selector_pattern = re.compile(
        r'(?:^|(?<=[\}\s]))((?:html|body)(?:\s*,\s*(?:html|body))*)\s*\{([^}]+)\}',
        re.IGNORECASE | re.DOTALL
    )

    extracted_backgrounds = {}

    def split_declarations(content: str) -> list[str]:
        decls = []
        current = []
        in_parens = 0
        in_single_quote = False
        in_double_quote = False
        for char in content:
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif char == '(' and not in_single_quote and not in_double_quote:
                in_parens += 1
            elif char == ')' and not in_single_quote and not in_double_quote:
                in_parens -= 1
            
            if char == ';' and in_parens == 0 and not in_single_quote and not in_double_quote:
                decls.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            decls.append("".join(current).strip())
        return [d for d in decls if d]

    for match in selector_pattern.finditer(css):
        block_content = match.group(2)
        decls = split_declarations(block_content)
        for decl in decls:
            parts = decl.split(":", 1)
            if len(parts) == 2:
                prop = parts[0].strip().lower()
                val = parts[1].strip()
                if prop.startswith("background"):
                    # Check for incompatibility: background-attachment or fixed values
                    if prop == "background-attachment" or "fixed" in val.lower():
                        continue
                    # Remove !important if present
                    val_sanitized = re.sub(r'\s*!\s*important\b', '', val, flags=re.IGNORECASE).strip()
                    extracted_backgrounds[prop] = val_sanitized

    if extracted_backgrounds:
        # Build the background declarations string to inject
        bg_lines = []
        for prop, val in extracted_backgrounds.items():
            bg_lines.append(f"    {prop}: {val};")
        bg_css = "\n".join(bg_lines) + "\n"

        # Now let's inject bg_css into the first @page rule.
        page_match = re.search(r'@page\s*\{', css)
        if page_match:
            idx = page_match.end()
            css = css[:idx] + "\n" + bg_css + css[idx:]
        else:
            # Prepend a new @page rule if none existed
            css = f"@page {{\n{bg_css}}}\n" + css

    # Step B: Inject transparency with highest priority at the end of CSS
    transparency_rule = """
/* Continuous Fusion Background Fix */
html, body, html body {
    background: transparent !important;
    background-image: none !important;
    background-color: transparent !important;
}
"""
    css += transparency_rule
    return css


def get_stylesheet(slug: str, custom_css: str = "", for_preview: bool = False) -> str:
    """Return the concatenated CSS for a theme.

    When slug is 'custom', base.css is prepended to the caller-supplied CSS.
    """
    if slug == "custom" or slug.startswith("preset:"):
        base = _read(_THEMES_DIR / "base.css")
        if custom_css.strip():
            patched = _inject_page_background(custom_css)
            full_css = f"{base}\n{patched}"
        else:
            full_css = base
    else:
        if not is_valid(slug):
            slug = "github"
        base = _read(_THEMES_DIR / "base.css")
        theme = _read(_THEMES_DIR / f"{slug}.css")
        full_css = f"{base}\n{theme}"

    if not for_preview:
        full_css = apply_continuous_fusion(full_css)

    return full_css


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
    full_css = get_stylesheet(slug, custom_css, for_preview=True)

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
