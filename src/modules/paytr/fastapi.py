"""Ready-to-use FastAPI routes for PayTR.

Mount every PayTR endpoint with one call::

    from paytr import PayTRClient
    from paytr.fastapi import include_paytr_routes

    client = PayTRClient(merchant_id=..., merchant_key=..., merchant_salt=...)

    async def on_payment(data):
        if data.is_success:
            ...  # credit the order — idempotent per merchant_oid

    include_paytr_routes(app, client, on_payment=on_payment)

This adds, under ``/paytr`` (configurable):

    POST /paytr/pay              create a V2 iFrame token (STEP 1)
    POST /paytr/callback         payment result callback (STEP 2, PayTR -> you)
    GET  /paytr/ok, /paytr/fail  default buyer redirect targets

These are exactly what the buyer needs to complete a purchase — nothing more.
Critical merchant-only operations (**refund**, **status query**, and the
**reporting** endpoints) are deliberately *not* exposed as routes: call
``client.refund()`` / ``client.status()`` / ``client.transaction_detail()`` etc.
on :class:`PayTRClient` directly from your own trusted server-side / admin code.

Requires ``fastapi`` (``pip install 'paytr-python[fastapi]'``).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Literal

try:
    from fastapi import APIRouter, FastAPI, Request
    from fastapi.responses import JSONResponse, PlainTextResponse
    from pydantic import BaseModel, ConfigDict, Field
except ImportError as e:  # pragma: no cover - import guard
    raise ImportError(
        "fastapi is required for paytr.fastapi. "
        "Install it with: pip install 'paytr-python[fastapi]'"
    ) from e

from ._log import logger
from .client import PayTRClient, PaymentType, iframe_url
from .errors import describe
from .exceptions import PayTRAPIError, PayTRError

Currency = Literal["TL", "TRY", "USD", "EUR", "GBP", "RUB"]
Lang = Literal["tr", "en"]


# --- request / response models (pydantic v2) --------------------------------
class BasketLine(BaseModel):
    name: str
    unit_price: float = Field(gt=0)  # major units, e.g. 34.56
    quantity: int = Field(1, ge=1)


class PaymentRequest(BaseModel):
    email: str = Field(max_length=100)
    user_name: str = Field(max_length=60)
    user_address: str = Field(max_length=400)
    user_phone: str = Field(max_length=20)
    basket: list[BasketLine] = Field(min_length=1)
    merchant_oid: str | None = Field(default=None, max_length=64)
    currency: Currency = "TL"
    lang: Lang = "tr"
    dark_mode: bool = False
    payment_type: PaymentType = "card"  # "eft" = Havale/EFT bank-transfer iFrame

    @property
    def total(self) -> float:
        return sum(item.unit_price * item.quantity for item in self.basket)


class CallbackData(BaseModel):
    """The form PayTR POSTs to the callback URL (extra fields preserved)."""

    model_config = ConfigDict(extra="allow")

    merchant_oid: str
    status: str
    total_amount: str
    hash: str
    failed_reason_code: str | None = None
    failed_reason_msg: str | None = None
    test_mode: str | None = None
    payment_type: str | None = None
    currency: str | None = None
    payment_amount: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def is_test(self) -> bool:
        return self.test_mode == "1"

    @property
    def error_message(self) -> str:
        """Human-readable failure reason (from PayTR or the error-code table)."""
        return self.failed_reason_msg or describe("payment", self.failed_reason_code)


CallbackHandler = Callable[[CallbackData], Awaitable[None]]


def get_client_ip(request: Request) -> str:
    """Best-effort external client IP (honours common proxy headers)."""
    forwarded = request.headers.get("CF-Connecting-IP") or request.headers.get(
        "X-Forwarded-For", ""
    )
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def generate_oid() -> str:
    """A unique, alphanumeric merchant order id (32 chars)."""
    return uuid.uuid4().hex.upper()


def _error_response(exc: PayTRError) -> JSONResponse:
    if isinstance(exc, PayTRAPIError):
        body = {"status": "failed", "reason": exc.message}
        if exc.code is not None:
            body["code"] = exc.code
        return JSONResponse(body, status_code=400)
    return JSONResponse({"status": "error", "reason": str(exc)}, status_code=502)


def create_paytr_router(
    client: PayTRClient,
    *,
    on_payment: CallbackHandler,
    prefix: str = "/paytr",
    ok_url: str | None = None,
    fail_url: str | None = None,
    tags: list[str] | None = None,
) -> APIRouter:
    """Build an :class:`APIRouter` with only the buyer-facing PayTR routes.

    Exposes ``/pay``, ``/callback`` and the ``/ok`` / ``/fail`` redirect targets.
    Merchant operations (refund, status, reporting, links, stored cards, BIN /
    installment queries, direct payment) are intentionally *not* routed — drive
    them from ``PayTRClient`` in your own backend.

    Args:
        client: a configured :class:`PayTRClient`.
        on_payment: ``async (CallbackData) -> None`` run for each verified
            callback. Must be idempotent per ``merchant_oid``: PayTR retries
            until it gets ``OK``, and if your handler raises we return non-200
            so PayTR re-sends — your handler may therefore see the same oid more
            than once.
        prefix: URL prefix for all routes (default ``/paytr``).
        ok_url / fail_url: buyer redirect URLs. Default to the router's own
            ``{prefix}/ok`` and ``{prefix}/fail``.
    """
    router = APIRouter(prefix=prefix, tags=tags or ["paytr"])
    base = prefix.rstrip("/")

    # -- STEP 1: create iFrame token ---------------------------------------
    @router.post("/pay")
    async def pay(request: Request, body: PaymentRequest) -> JSONResponse:
        root = str(request.base_url)
        try:
            result = await client.create_iframe_token(
                merchant_oid=body.merchant_oid or generate_oid(),
                email=body.email,
                payment_amount=body.total,
                user_ip=get_client_ip(request),
                user_name=body.user_name,
                user_address=body.user_address,
                user_phone=body.user_phone,
                user_basket=[(i.name, i.unit_price, i.quantity) for i in body.basket],
                merchant_ok_url=ok_url or f"{root}{base.lstrip('/')}/ok",
                merchant_fail_url=fail_url or f"{root}{base.lstrip('/')}/fail",
                currency=body.currency,
                lang=body.lang,
                dark_mode=body.dark_mode,
                payment_type=body.payment_type,
            )
        except PayTRError as e:
            return _error_response(e)
        return JSONResponse(
            {
                "status": "success",
                "merchant_oid": result["merchant_oid"],
                "token": result["token"],
                "iframe_url": iframe_url(result["token"]),
            }
        )

    # -- STEP 2: callback ---------------------------------------------------
    @router.post("/callback", response_class=PlainTextResponse)
    async def callback(request: Request) -> PlainTextResponse:
        try:
            data = CallbackData(**dict(await request.form()))
        except Exception:
            return PlainTextResponse(
                "PAYTR notification failed: validation error", status_code=400
            )
        if not client.verify_callback(
            merchant_oid=data.merchant_oid,
            status=data.status,
            total_amount=data.total_amount,
            hash=data.hash,
        ):
            return PlainTextResponse(
                "PAYTR notification failed: bad hash", status_code=400
            )
        try:
            await on_payment(data)
        except Exception:
            # PayTR retries until it receives the body "OK". Returning "OK" here
            # would tell it to stop — losing the notification if our handler
            # failed. Return non-200 so PayTR re-sends the callback later.
            logger.exception("on_payment failed for oid=%s; asking PayTR to retry", data.merchant_oid)
            return PlainTextResponse("retry", status_code=500)
        return PlainTextResponse("OK")

    # -- default redirect targets ------------------------------------------
    @router.get("/ok")
    async def ok() -> dict:
        return {"status": "success", "message": "Payment completed."}

    @router.get("/fail")
    async def fail() -> dict:
        return {"status": "failed", "message": "Payment failed."}

    return router


def include_paytr_routes(
    app: FastAPI,
    client: PayTRClient,
    *,
    on_payment: CallbackHandler,
    prefix: str = "/paytr",
    ok_url: str | None = None,
    fail_url: str | None = None,
    tags: list[str] | None = None,
) -> APIRouter:
    """Convenience wrapper: build the router and mount it on ``app``.

    Returns the router (already included) for further inspection.
    """
    router = create_paytr_router(
        client,
        on_payment=on_payment,
        prefix=prefix,
        ok_url=ok_url,
        fail_url=fail_url,
        tags=tags,
    )
    app.include_router(router)
    return router
