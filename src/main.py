from dotenv import load_dotenv

load_dotenv()  # credentials from .env (see src/example.env)

import importlib
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_SRC = Path(__file__).parent
# Make the library under modules/ importable by its public name: `import paytr`.
sys.path.insert(0, str(_SRC / "modules"))

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importing paytr auto-configures the [PAYTR] logger (no setup call needed).
from paytr import logger as log

# Any api/ module containing this line is treated as a route module.
ROUTER_MARKER = "from fastapi import APIRouter"


# MARK: Lifespan — close the shared PayTR client on shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from paytr._client import client

    await client.aclose()


# MARK: Auto-discover routers — mount every api/ module that defines an APIRouter
def _include_routers(app: FastAPI, package: str = "api") -> None:
    for py in sorted((_SRC / package).glob("*.py")):
        if ROUTER_MARKER not in py.read_text(encoding="utf-8"):
            continue
        mod_name = f"{package}.{py.stem}"
        router = getattr(importlib.import_module(mod_name), "router", None)
        if isinstance(router, APIRouter):
            app.include_router(router)
            log.info("Mounted %s (%d routes)", mod_name, len(router.routes))
        else:
            log.warning("Skipped %s: no APIRouter named 'router'", mod_name)


app = FastAPI(title="paytr-python", version="0.1.1", lifespan=lifespan)
# Permissive CORS so web/index.html works even when opened directly as a file.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_include_routers(app)


# MARK: Dev launcher — run from src/:  uv run main.py
if __name__ == "__main__":
    import subprocess

    print("Starting dev server at http://localhost:8000/paytr/")
    subprocess.run(
        ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        check=True,
    )
