"""GET /paytr/ — serve the PayTR test page (demo only).

Kept under the /paytr prefix so it never collides with the host app's own root.
The ok/fail redirect targets come from the library router (paytr.fastapi).
"""

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

log = logging.getLogger("paytr")

router = APIRouter(prefix="/paytr", tags=["paytr"])

# src/api/page.py -> parents[1] == src
_INDEX = Path(__file__).resolve().parents[1] / "web" / "index.html"


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    try:
        return HTMLResponse(_INDEX.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log.error("Test page not found at %s", _INDEX)
        return HTMLResponse("<h1>Test page not found</h1>", status_code=404)
