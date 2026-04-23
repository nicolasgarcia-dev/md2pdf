"""FastAPI entry point."""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .ratelimit import enforce
from .rendering.chromium import chromium
from .rendering.dispatcher import render
from .rendering.themes import THEMES, get_preview_stylesheet, is_valid
from .security import BYPASS_COOKIE_NAME, is_privileged

logger = logging.getLogger("md2pdf")
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        await chromium.stop()


app = FastAPI(title="md2pdf", version="1.0.0", lifespan=lifespan)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


def _effective_max_markdown(request: Request) -> int:
    return settings.owner_max_markdown_bytes if is_privileged(request) else settings.max_markdown_bytes


def _effective_max_upload(request: Request) -> int:
    return settings.owner_max_upload_bytes if is_privileged(request) else settings.max_upload_bytes


class RenderRequest(BaseModel):
    markdown: str = Field(..., description="Raw Markdown source")
    theme: str = Field("github", description="Theme slug")
    title: str = Field("document", max_length=120)
    include_toc: bool = True
    force_high_fidelity: bool = False
    custom_css: str = Field("", description="Custom CSS (only used when theme='custom')")


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(title: str) -> str:
    cleaned = _SAFE_FILENAME_RE.sub("_", title).strip("_") or "document"
    return f"{cleaned[:80]}.pdf"


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/themes")
async def list_themes() -> list[dict[str, str]]:
    return [{"slug": t.slug, "name": t.name, "description": t.description} for t in THEMES]


@app.get("/api/themes/{slug}/css")
async def theme_preview_css(slug: str) -> Response:
    """Return theme CSS scoped to #preview for the live preview pane."""
    if not is_valid(slug) or slug == "custom":
        slug = "github"
    css = get_preview_stylesheet(slug)
    return Response(content=css, media_type="text/css",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.post("/api/render", dependencies=[Depends(enforce)])
async def render_markdown(request: Request, payload: RenderRequest = Body(...)) -> Response:
    max_bytes = _effective_max_markdown(request)
    if len(payload.markdown.encode("utf-8")) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Markdown payload too large.")
    if not is_valid(payload.theme):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown theme.")
    result = await render(
        payload.markdown,
        theme=payload.theme,
        title=payload.title or "document",
        include_toc=payload.include_toc,
        force_high_fidelity=payload.force_high_fidelity,
        custom_css=payload.custom_css,
    )
    filename = _safe_filename(payload.title or "document")
    return Response(
        content=result.pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Render-Engine": result.engine,
        },
    )


@app.post("/api/upload", dependencies=[Depends(enforce)])
async def render_upload(
    request: Request,
    file: UploadFile = File(...),
    theme: str = Form("github"),
    title: str = Form("document"),
    include_toc: bool = Form(True),
    force_high_fidelity: bool = Form(False),
) -> Response:
    max_bytes = _effective_max_upload(request)
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Uploaded file too large.")
    try:
        markdown = data.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File must be UTF-8 text.")
    if not is_valid(theme):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown theme.")

    # Prefer the uploaded filename (sans extension) over the default title.
    derived_title = title or Path(file.filename or "document").stem or "document"
    result = await render(
        markdown,
        theme=theme,
        title=derived_title,
        include_toc=include_toc,
        force_high_fidelity=force_high_fidelity,
    )
    filename = _safe_filename(derived_title)
    return Response(
        content=result.pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Render-Engine": result.engine,
        },
    )


def _token_matches(supplied: Optional[str]) -> bool:
    import hmac
    configured = settings.bypass_token
    if not configured or not supplied:
        return False
    return hmac.compare_digest(configured.encode("utf-8"), supplied.encode("utf-8"))


def _install_bypass_cookie(response: Response) -> None:
    response.set_cookie(
        BYPASS_COOKIE_NAME,
        settings.bypass_token,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


@app.post("/api/bypass/activate")
async def activate_bypass(token: Optional[str] = Body(None, embed=True)) -> JSONResponse:
    """Install the bypass cookie if the supplied token matches.

    Silent behaviour on failure: the response is the same 404 a normal
    visitor would see on any unknown route, to avoid leaking the endpoint's
    existence via timing or status codes.
    """
    if not _token_matches(token):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    response = JSONResponse({"ok": True})
    _install_bypass_cookie(response)
    return response


# Minimal unstyled form at /bypass so the owner can type the token on a
# device where sending POSTs is awkward. Returns 404 when the feature is
# disabled, so its presence is not detectable by scanners.
_BYPASS_FORM = (
    "<!doctype html><meta charset=utf-8><title>.</title>"
    "<form method=POST action=/bypass style='font-family:sans-serif;max-width:320px;margin:10vh auto'>"
    "<input type=password name=token autocomplete=current-password autofocus "
    "style='width:100%;padding:10px;font-size:16px;box-sizing:border-box'>"
    "<button type=submit style='margin-top:10px;padding:10px 16px;font-size:16px'>OK</button>"
    "</form>"
)


@app.get("/bypass")
async def bypass_form() -> HTMLResponse:
    if not settings.bypass_token:
        return HTMLResponse("Not Found", status_code=404)
    return HTMLResponse(_BYPASS_FORM)


@app.post("/bypass")
async def bypass_submit(token: str = Form(...)) -> Response:
    if not _token_matches(token):
        return HTMLResponse("Not Found", status_code=404)
    response = RedirectResponse("/", status_code=303)
    _install_bypass_cookie(response)
    return response


@app.get("/")
async def index(request: Request) -> Response:
    # If a ?k=TOKEN is presented and matches, install the cookie and
    # redirect to a clean URL so the token is not visible in the address
    # bar or browser history afterwards.
    k = request.query_params.get("k")
    if k is not None and _token_matches(k):
        response = RedirectResponse("/", status_code=303)
        _install_bypass_cookie(response)
        return response
    return FileResponse(_FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")
