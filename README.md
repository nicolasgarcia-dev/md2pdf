
# md2pdf

A fast, self-hosted web application that instantly converts Markdown into beautifully formatted PDF documents. 

It provides a clean, live-preview editor out-of-the-box and features intelligent rendering: simple documents use **WeasyPrint** for lightning-fast, size-efficient PDFs, while complex documents (like those with Mermaid diagrams) seamlessly fall back to **Chromium via Playwright** to ensure perfect fidelity.

---

## Features

- **Live Preview Editor:** See your changes in real-time as you type, mirroring the final PDF output.
- **Rich Markdown Support:** Full formatting support including tables, syntax-highlighted code blocks, and automatic Table of Contents (`[[toc]]`).
- **Math & Diagrams:** Built-in support for KaTeX formatting (`$...$`, `$$...$$`) and Mermaid diagrams via fenced ` ```mermaid ` blocks.
- **Native Emoji Support:** Full Unicode emoji integration using high-quality bundled fonts.
- **Multiple Themes:** Choose from various professional typography presets (see [Themes](#-themes)).
- **Size-Aware Rendering:** Automatically picks the most efficient rendering engine to save resources and produce text-selectable PDFs.
- **RESTful API:** Deploy as a microservice and generate PDFs programmatically.

## Themes

`md2pdf` ships with several hand-crafted typographic themes. You can easily select your preferred theme in the UI or specify it via the API:

- **GitHub:** Familiar, clean styling matching GitHub's markdown rendering.
- **Academic:** Classic serif typography perfect for papers and formal documentation.
- **Minimal:** Ultra-clean, distraction-free styling with plenty of whitespace.
- **Elegant:** Sophisticated sans-serif typography for modern reports.
- **Modern:** Bold, highly readable structure with refined accents.

## Deployment (Docker)

The easiest and recommended way to run `md2pdf` is using Docker. Our container is fully self-contained, bundling `WeasyPrint`, `Chromium`, and all necessary system fonts. It is designed to be architecture-agnostic and will run cleanly on any modern server.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/nicolasgarcia-dev/md2pdf.git
   cd md2pdf
   ```

2. **Prepare the environment:**
   ```bash
   cp .env.example .env
   ```
   *(Optional) You can edit `.env` to tweak upload limits, rate bounds, and API ports.*

3. **Start the container:**
   ```bash
   docker compose up -d --build
   ```

The application will be instantly available at `http://localhost:8000`.

### Security Note
The setup is hard-configured for maximum security by default: the container drops all capabilities (`cap_drop: ALL`), enforces `no-new-privileges`, limits RAM and PIDs, and runs an absolutely strict read-only filesystem (with tiny `tmpfs` mounts purely for rendering caches). It is safe to expose via a reverse proxy.

## 🛠 Usage & API

You can use the built-in web frontend by visiting `http://localhost:8000`, or you can integrate `md2pdf` into your existing pipelines using its REST API:

- `GET /api/themes`: Retrieve a list of all available themes.
- `POST /api/render`: Render a markdown string.
  - Payload: `{ "markdown": "# Hello", "theme": "github", "force_high_fidelity": false }`
  - Returns: The binary PDF data.
- `POST /api/upload`: Upload a `.md` or `.txt` file via multipart form-data to receive a PDF.
- `GET /healthz`: Liveness probe for orchestration and uptime monitoring.

*Note: The application applies configurable per-IP rate limiting to prevent abuse if exposed publicly.*

## Local Development

If you prefer to run the application directly on your host machine without Docker (Requires Python 3.11+):

```bash
# 1. Install system dependencies (Debian/Ubuntu example)
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libcairo2 libgdk-pixbuf-2.0-0 fonts-noto-color-emoji fonts-noto

# 2. Set up the Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 3. Install Playwright browser dependencies
python -m playwright install --with-deps chromium

# 4. Configure environment variables
cp .env.example .env

# 5. Run the server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

## License

Released under the MIT License.
