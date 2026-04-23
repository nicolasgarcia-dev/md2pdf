# md2pdf

A small self-hosted web application that converts Markdown into PDF. It
provides a clean editor with live preview, several typographic presets,
math rendering through KaTeX, diagrams through Mermaid, syntax-highlighted
code blocks, automatic tables of contents and full emoji support.

The backend picks the lightest renderer that still produces a faithful
document: simple documents are rendered by WeasyPrint (no headless browser,
small PDFs, fully selectable text), while documents that require JavaScript
execution (currently Mermaid diagrams, or when the user forces high
fidelity mode) fall back to a headless Chromium via Playwright.

## Features

- Paste Markdown or upload a `.md` / `.markdown` / `.txt` file.
- Live client-side preview that mirrors the final PDF.
- Multiple built-in themes (GitHub, Academic, Minimal, Elegant, Modern).
- KaTeX math, inline (`$...$`) and display (`$$...$$`).
- Mermaid diagrams in fenced ` ```mermaid ` blocks.
- Syntax highlighting for fenced code blocks.
- Automatic table of contents with clickable anchors.
- Native Unicode emoji, rendered through a bundled color emoji font.
- Selectable text whenever the underlying content allows it.
- Size-aware rendering: the smaller WeasyPrint path is used by default;
  Chromium is only used when the document needs it.

## Quick start (local development)

Requirements: Python 3.11+, Node is not required.

```bash
# System dependencies for WeasyPrint (Debian/Ubuntu)
sudo apt-get install -y \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
    libcairo2 libgdk-pixbuf-2.0-0 fonts-noto-color-emoji fonts-noto

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install --with-deps chromium

cp .env.example .env
# edit .env if desired

uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000 in a browser.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up -d --build
```

The container bundles WeasyPrint, Chromium (via Playwright) and the
required fonts.

## API

The frontend is a thin client over a small JSON/binary API:

- `GET /api/themes` returns the available themes.
- `POST /api/render` accepts `{ "markdown": "...", "theme": "github", "force_high_fidelity": false }` and returns a PDF.
- `POST /api/upload` accepts a multipart file upload and returns a PDF.
- `GET /healthz` returns a liveness probe.

A per-IP rate limit is applied to `/api/render` and `/api/upload`.

## License

MIT. See `LICENSE` if provided.
