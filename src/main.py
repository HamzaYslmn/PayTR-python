from dotenv import load_dotenv

load_dotenv()  # credentials from .env (see src/example.env)

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make the library under modules/ importable by its public name: `import paytr`.
sys.path.insert(0, str(Path(__file__).parent / "modules"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# MARK: Lifespan — close the shared PayTR client on shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from api._client import client

    await client.aclose()


app = FastAPI(title="paytr-python", version="0.2.0", lifespan=lifespan)
# Permissive CORS so web/index.html works even when opened directly as a file.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from api import page, payment  # noqa: E402  (needs the sys.path insert above)

app.include_router(page.router)
app.include_router(payment.router)


# MARK: Dev launcher — run from src/:  uv run main.py
if __name__ == "__main__":
    import uvicorn

    print("Starting dev server at http://localhost:8000/paytr/")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
