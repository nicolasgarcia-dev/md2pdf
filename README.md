# md2pdf

A fast, self-hosted web app that turns Markdown into beautifully formatted PDFs.

It ships with a live-preview editor, multi-document workspace, themeable typography, KaTeX math, Mermaid diagrams, syntax highlighting, and a full CSS playground for designing your own theme. Documents and saved style presets live in your browser's local storage — the server only sees the Markdown you submit at render time, and never persists it.

Rendering is done by **headless Chromium** (via Playwright) for full fidelity, with **WeasyPrint** as an automatic fallback if Chromium is unavailable. Both engines consume the same self-contained HTML, so output is consistent regardless of which one runs.

---

## Features

- **Live preview editor** with GitHub-flavored Markdown (tables, task lists, footnotes, autolinks).
- **Multi-document sidebar.** Multiple documents persist locally, each autosaved as you type.
- **KaTeX math.** Inline `$E=mc^2$` and display `$$ \int … $$`, including matrices.
- **Mermaid diagrams** rendered both in the preview and the PDF.
- **Syntax highlighting** unified across both renderers (highlight.js in the preview, Pygments in the PDF).
- **Six built-in themes** — *GitHub, Academic, Minimal, Elegant, Modern,* and a *Custom CSS* playground.
- **Save your styles.** Any Custom CSS configuration can be saved as a named preset that joins the theme dropdown.
- **Scale slider** (60 %–140 %) to compress or expand the rendered PDF without touching its content.
- **Toggleable table of contents** generated automatically from the document headings.
- **Locked / unlocked scroll sync** between editor and preview.
- **Upload .md / Download PDF** from anywhere on the toolbar; drag-and-drop a `.md` file onto the editor to load it.
- **Privacy by design.** Documents and presets stay in your browser's `localStorage`; the only server round-trip happens when you click *Download PDF*, and the file is rendered on the fly and discarded.
- **REST API** so you can integrate it into pipelines without the UI.

---

## Quick start (Docker)

```bash
git clone https://github.com/nicolasgarcia-dev/md2pdf.git
cd md2pdf
cp .env.example .env
docker compose up -d --build
```

The app is then available at http://localhost:8000.

The container ships **WeasyPrint, Chromium, and all required system fonts**, drops every Linux capability (`cap_drop: ALL`), enables `no-new-privileges`, caps RAM and PIDs, runs a read-only filesystem with tiny `tmpfs` mounts for render scratch, and runs as an unprivileged user. It is safe to expose behind a reverse proxy.

---

## UI tour

| Area | What it does |
| --- | --- |
| **Toolbar** | Title, theme picker, scale (%), TOC toggle, scroll-sync toggle, shortcut help, upload, download. |
| **Documents sidebar** (top-left, `Ctrl+\``) | List, rename, delete and create documents. The `+` and `Ctrl+Alt+N` always start a new doc seeded with the onboarding tour. |
| **Editor** | Markdown source. Drag `.md` files in to load them. |
| **Preview** | Live-rendered HTML. Mirrors the PDF as closely as the renderer permits. |
| **Custom CSS panel** | Appears when *Theme* is set to *Custom CSS* (or to a saved preset). Includes a **bookmark** button to save the current CSS as a named preset (added to the theme dropdown under *Saved*) and a **trash** button to delete the active preset. |
| **? button / `?` shortcut** | Toggle the keyboard shortcut panel. Click again or press `Esc` to close. |

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl + S` | Download PDF |
| `Ctrl + Alt + N` | New document |
| `Ctrl + Z` / `Ctrl + Shift + Z` | Undo / Redo |
| `Ctrl + B` / `Ctrl + I` | Bold / Italic selection |
| `Ctrl + K` | Wrap selection in a Markdown link |
| `Ctrl + A` / `Ctrl + C` / `Ctrl + X` / `Ctrl + V` | Standard select / copy / cut / paste |
| `Ctrl + \`` | Toggle the documents sidebar |
| `Tab` / `Shift + Tab` | Indent / outdent at caret (or block-indent multi-line selection) |
| `?` | Toggle the shortcuts panel (only when no text field is focused) |

---

## REST API

The API powers the UI and can be used standalone for batch jobs.

### `GET /api/themes`
Returns the catalogue:
```json
[
  {"slug": "github", "name": "GitHub", "description": "..."},
  {"slug": "academic", "name": "Academic", "description": "..."},
  {"slug": "minimal", "name": "Minimal", "description": "..."},
  {"slug": "elegant", "name": "Elegant", "description": "..."},
  {"slug": "modern", "name": "Modern", "description": "..."},
  {"slug": "custom", "name": "Custom CSS", "description": "..."}
]
```

### `GET /api/themes/{slug}/css`
Returns the theme stylesheet, scoped to `#preview`. Used by the live preview.

### `POST /api/render`
Render a Markdown payload to PDF.

```json
{
  "markdown":   "# Hello\n\nWorld",
  "theme":      "github",
  "title":      "document",
  "include_toc": true,
  "custom_css": "",
  "scale":       1.0
}
```

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `markdown` | string | — | Required. Capped by `MAX_MARKDOWN_BYTES`. |
| `theme` | string | `github` | One of the slugs returned by `/api/themes`. Use `custom` to apply `custom_css`. |
| `title` | string | `document` | Used for the PDF filename and `<title>`. Max 120 chars. |
| `include_toc` | bool | `true` | Auto-generates a TOC from headings. |
| `custom_css` | string | `""` | Honoured only when `theme = "custom"`. |
| `scale` | float | `1.0` | `0.6`–`1.4`. WeasyPrint fallback ignores this and renders at `1.0`. |

Returns `application/pdf`. The response carries an `X-Render-Engine` header set to `chromium` or `weasyprint` depending on which engine produced the document.

### `POST /api/upload`
Multipart form upload of a `.md` / `.txt` file. Same fields as `/api/render` (without `markdown` and `custom_css`); the file body is the Markdown source.

### `GET /healthz`
Liveness probe.

### Limits and rate limiting
All write endpoints apply per-IP rate limits configured via `.env` (see [Configuration](#configuration)). When the optional **owner bypass** is enabled, requests carrying the bypass cookie or `X-Bypass-Token` header skip rate limits and use the higher `OWNER_MAX_*` size caps.

---

## Themes and Custom CSS

`base.css` defines the page geometry, typography reset, table of contents, blockquote treatment and a *syntax-highlighting palette* exposed as CSS custom properties:

```css
pre, .codehilite {
  --syn-keyword:  #cf222e;
  --syn-string:   #0a3069;
  --syn-comment:  #6e7781;
  --syn-number:   #0550ae;
  --syn-function: #8250df;
  --syn-builtin:  #0550ae;
  --syn-operator: #cf222e;
  --syn-type:     #0550ae;
  --syn-attr:     #0550ae;
  --syn-meta:     #8250df;
}
```

Each per-theme stylesheet (`github.css`, `academic.css`, …) overrides those variables along with `body`, headings, links, blockquote, tables, code chip, `pre` background and the TOC, so PDF + preview stay visually consistent. The variables drive both renderers — Pygments classes in the PDF and highlight.js classes in the preview map to the same set, so a single override styles both at once.

When the user picks **Custom CSS** in the theme dropdown, their stylesheet is loaded *after* the base + theme styles, so anything can be overridden. The frontend also auto-extends `html, body { background: … }` into an `@page { background-color: … }` rule so the page gutters match the content area without the user needing to write print-specific rules.

The in-app help panel (the `?` button inside the Custom CSS header) documents every selector, the syntax-highlighting palette, page-layout rules, and includes ready-to-paste examples for warm cream, slate dark, dark academia and Catppuccin-Mocha-flavored code blocks.

---

## Adding more fonts

Fonts are installed at image build time via `apt-get` in the [`Dockerfile`](Dockerfile). Both renderers (WeasyPrint and Chromium) discover them automatically through fontconfig — there is nothing to register inside the app.

### Steps

1. **Add the Debian package(s)** to the `apt-get install` block in the `Dockerfile`. Example:

   ```dockerfile
   RUN apt-get update && apt-get install -y --no-install-recommends \
           libpango-1.0-0 \
           libpangoft2-1.0-0 \
           libharfbuzz0b \
           libcairo2 \
           libgdk-pixbuf-2.0-0 \
           libffi8 \
           shared-mime-info \
           fonts-noto \
           fonts-noto-cjk \
           fonts-noto-color-emoji \
           fonts-inter \
           fonts-jetbrains-mono \
           fontconfig \
           fonts-firacode \                  # ← new
           fonts-ibm-plex \                  # ← new
           ca-certificates curl \
       && rm -rf /var/lib/apt/lists/*
   ```

2. **Update the visible list** in [`frontend/index.html`](frontend/index.html) (search for `help-font-list`) so users know which `font-family` names are available:

   ```html
   <span style="font-family:'Fira Code',monospace">Fira Code</span>
   <span style="font-family:'IBM Plex Sans',sans-serif">IBM Plex Sans</span>
   ```

3. **Rebuild the image:**

   ```bash
   docker compose up -d --build
   ```

### Useful Debian font packages

| Package | Family | Style |
| --- | --- | --- |
| `fonts-source-sans3` | Source Sans 3 | Sans |
| `fonts-source-code-pro` | Source Code Pro | Mono |
| `fonts-merriweather` | Merriweather | Serif |
| `fonts-crimson` | Crimson Text | Serif |
| `fonts-ibm-plex` | IBM Plex Sans/Serif/Mono | Suite |
| `fonts-roboto` | Roboto | Sans |
| `fonts-firacode` | Fira Code | Mono with ligatures |
| `fonts-cascadia-code` | Cascadia Code | Mono |
| `fonts-dejavu` | DejaVu | Broad coverage |

Each package adds roughly 5–20 MB to the final image. The defaults shipped today are:

- **Sans:** Noto Sans, Inter
- **Serif (transitional):** Noto Serif
- **Serif (old-style):** EB Garamond
- **Slab serif:** Roboto Slab
- **Mono:** JetBrains Mono
- **Color emoji:** Noto Color Emoji
- **CJK:** Noto CJK

### Bundling a font without a Debian package

If the font you want isn't packaged in Debian, drop the `.ttf` / `.otf` files into a directory under `/usr/local/share/fonts/` and run `fc-cache -f` afterwards:

```dockerfile
# Either copy local files into the image…
COPY my-fonts/ /usr/local/share/fonts/myfonts/
RUN fc-cache -f /usr/local/share/fonts

# …or fetch them at build time from upstream.
RUN mkdir -p /usr/local/share/fonts/extra \
    && curl -fsSL -o /usr/local/share/fonts/extra/Inter-Regular.ttf \
       https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Regular.otf \
    && fc-cache -f /usr/local/share/fonts
```

Same idea either way: WeasyPrint and Chromium pick them up automatically through fontconfig.

---

## Privacy and data flow

- The Markdown editor and the *Saved* CSS presets are persisted in the browser's `localStorage` under the keys `md2pdf:docs`, `md2pdf:active-doc`, `md2pdf:custom-css`, `md2pdf:css-presets`, `md2pdf:active-theme`, `md2pdf:scale`, `md2pdf:sidebar-open`, `md2pdf:sync-scroll`. Nothing is sent to the server while you write.
- **Only the render endpoint** (`POST /api/render` / `/api/upload`) ever receives the Markdown. The server renders the PDF in-memory, streams it back, and discards both the input and the output. No request bodies, generated PDFs or telemetry are written to disk.
- Logs at `INFO` level only record method, path, status code and engine. They do not include the Markdown payload.
- The optional bypass cookie is `HttpOnly`, `Secure`, `SameSite=Strict`.

---

## Configuration

All settings live in `.env` (a starter is in `.env.example`). Highlights:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_HOST` / `APP_PORT` / `APP_WORKERS` | `0.0.0.0` / `8000` / `2` | uvicorn binding. |
| `LOG_LEVEL` | `info` | Application log level. |
| `MAX_MARKDOWN_BYTES` | `5 MiB` | Per-request body cap. |
| `MAX_UPLOAD_BYTES` | `10 MiB` | Multipart upload cap. |
| `RATE_LIMIT_PER_MINUTE` / `_PER_HOUR` | `20` / `100` | Per-IP rate limits. |
| `BYPASS_TOKEN` | empty | If set, holders skip rate limits and use the higher `OWNER_MAX_*` caps. |
| `OWNER_MAX_MARKDOWN_BYTES` / `OWNER_MAX_UPLOAD_BYTES` | `20 MiB` / `50 MiB` | Caps for bypass users. |
| `TRUST_PROXY_HEADERS` | `true` | Honour `X-Forwarded-For` when behind Nginx Proxy Manager. |
| `CORS_ALLOW_ORIGINS` | empty | Comma-separated allowlist; empty = same-origin only. |

---

## Local development

Without Docker (Python 3.11+):

```bash
# 1. System libraries (Debian/Ubuntu example)
sudo apt-get install -y \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libcairo2 \
    libgdk-pixbuf-2.0-0 libffi8 shared-mime-info \
    fonts-noto fonts-noto-color-emoji fonts-noto-cjk \
    fonts-inter fonts-jetbrains-mono \
    fonts-ebgaramond fonts-roboto-slab

# 2. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 3. Chromium for high-fidelity rendering
python -m playwright install --with-deps chromium

# 4. Configuration
cp .env.example .env

# 5. Run
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

The frontend is plain HTML/CSS/JS served from `frontend/`. Edit and reload — there is no build step.

### Layout

```
backend/app/
├── main.py                  # FastAPI app, routes
├── config.py                # env-driven settings
├── ratelimit.py             # per-IP limiter
├── security.py              # owner bypass cookie
└── rendering/
    ├── markdown.py          # markdown-it + Pygments highlighting
    ├── document.py          # builds the standalone HTML
    ├── themes.py            # theme registry, base+per-theme CSS combiner
    ├── chromium.py          # Playwright integration
    ├── weasy.py             # WeasyPrint fallback
    └── dispatcher.py        # render() entry point (Chromium → WeasyPrint)

backend/app/assets/themes/
├── base.css                 # geometry, typography, syntax palette
├── github.css | academic.css | minimal.css | elegant.css | modern.css

frontend/
├── index.html               # editor + dialogs
├── style.css                # app chrome
└── app.js                   # editor, preview pipeline, presets, dialogs
```

---

## Contributing

PRs and issues welcome on [GitHub](https://github.com/nicolasgarcia-dev/md2pdf). If md2pdf is useful to you, a ⭐ on the repository goes a long way.

## License

MIT.
