FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# System dependencies:
#   - WeasyPrint: pango, cairo, harfbuzz, gdk-pixbuf
#   - Playwright/Chromium: fonts and graphics libs are installed by
#     "playwright install-deps" below
#   - Color emoji: fonts-noto-color-emoji
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
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Install Chromium and its OS dependencies via Playwright.
RUN python -m playwright install --with-deps chromium

COPY backend /app/backend
COPY frontend /app/frontend

RUN useradd --create-home --uid 10001 app \
    && chown -R app:app /app /ms-playwright
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
