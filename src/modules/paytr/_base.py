"""Shared plumbing for the PayTR API mixins.

Each ``*_api.py`` module defines a small mixin (``IframeMixin``, ``LinkMixin``,
…) that subclasses :class:`_BaseClient` and adds the methods for one PayTR API.
``PayTRClient`` in :mod:`paytr.client` composes them. Everything they share —
construction, the HTTP session lifecycle, signing-key access, the POST + JSON
decode, generic callback verification and error mapping, plus the amount/basket
encoders — lives here so each mixin stays focused on its own endpoints.

Amounts come in two flavours, matching what each PayTR endpoint expects:

* **minor-unit integer** (major units x 100): iFrame ``payment_amount`` and link
  ``price`` — built with :func:`_minor_units`.
* **major-unit string** (``"10.25"``): refund ``return_amount`` *and*
  ``direct_payment``'s ``payment_amount`` — built with :func:`_money`. Note this
  differs from the iFrame, which is the easy trap.
"""

from __future__ import annotations

import base64
import json
from decimal import ROUND_HALF_UP, Decimal
from types import TracebackType
from typing import Any, Literal

from . import _crypto
from .errors import Scope, describe
from .exceptions import PayTRAPIError, PayTRConfigError, PayTRNetworkError

# A basket line: (name, unit_price_in_major_units, quantity).
BasketLine = tuple[str, "str | float | Decimal", int]

# Card vs. Havale/EFT bank-transfer iFrame. Shared with paytr.fastapi.
PaymentType = Literal["card", "eft"]


def _detect_backend(client: Any) -> str:
    """Infer the HTTP backend from a user-supplied session object."""
    root = type(client).__module__.split(".")[0]
    if root == "aiohttp":
        return "aiohttp"
    if root == "httpx":
        return "httpx"
    raise PayTRConfigError(
        "client must be an aiohttp.ClientSession or an httpx.AsyncClient"
    )


def _normalize_currency(currency: str) -> str:
    """PayTR expects ``"TL"``; accept the ISO spelling ``"TRY"`` as an alias."""
    return "TL" if currency == "TRY" else currency


def _money(value: str | float | Decimal) -> str:
    """Format an amount in major units with two decimals and a '.' separator."""
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def _minor_units(value: str | float | Decimal) -> int:
    """Major units -> integer minor units (PayTR multiplies amounts by 100)."""
    cents = (Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def encode_basket(items: list[BasketLine]) -> str:
    """Base64-encode a basket for PayTR's ``user_basket`` field.

    Each item is ``(name, unit_price, quantity)`` with the price in major units
    (e.g. ``18.00``). Returns ``base64(json([[name, "18.00", qty], ...]))``.
    """
    basket = [[name, _money(price), int(qty)] for name, price, qty in items]
    return base64.b64encode(json.dumps(basket).encode()).decode()


class _BaseClient:
    """Construction, HTTP session lifecycle, signing-key access and helpers.

    Credentials live on the client; per-request data is passed to each method.
    Reuse one instance for connection pooling and close it on shutdown
    (``await client.aclose()``), or use it as an async context manager.

    HTTP session: bring your own for full control of timeouts, connection
    limits, proxies or retries — pass an ``aiohttp.ClientSession`` or an
    ``httpx.AsyncClient`` as ``session=`` (auto-detected; a session you pass in
    is never closed by us). With no session, a default ``aiohttp`` session is
    created lazily with ``timeout`` seconds — pass ``timeout=None`` to impose no
    timeout of our own.
    """

    def __init__(
        self,
        *,
        merchant_id: str,
        merchant_key: str | bytes,
        merchant_salt: str | bytes,
        test_mode: bool = False,
        debug_on: bool = False,
        default_no_installment: int = 0,
        default_max_installment: int = 0,
        default_timeout_limit: int = 30,
        session: Any | None = None,
        timeout: float | None = 30.0,
    ) -> None:
        if not merchant_id or not merchant_key or not merchant_salt:
            raise PayTRConfigError(
                "merchant_id, merchant_key and merchant_salt are all required"
            )
        self.merchant_id = str(merchant_id)
        self.merchant_key = merchant_key
        self.merchant_salt = merchant_salt
        self.test_mode = test_mode
        self.debug_on = debug_on
        self.default_no_installment = default_no_installment
        self.default_max_installment = default_max_installment
        self.default_timeout_limit = default_timeout_limit
        self._timeout = timeout

        if session is not None:
            self._session = session
            self._owns_session = False
            self._backend = _detect_backend(session)
        else:
            self._session = None  # default aiohttp session, created lazily
            self._owns_session = True
            self._backend = "aiohttp"

    @classmethod
    def from_env(cls, prefix: str = "PAYTR_", **overrides):
        """Build a client from ``PAYTR_MERCHANT_ID`` / ``_KEY`` / ``_SALT`` env
        vars (plus ``_TEST_MODE`` / ``_DEBUG_ON``, ``"1"`` = on). ``overrides``
        win over the environment."""
        import os

        env = {
            "merchant_id": os.environ.get(f"{prefix}MERCHANT_ID", ""),
            "merchant_key": os.environ.get(f"{prefix}MERCHANT_KEY", ""),
            "merchant_salt": os.environ.get(f"{prefix}MERCHANT_SALT", ""),
            "test_mode": os.environ.get(f"{prefix}TEST_MODE", "0") == "1",
            "debug_on": os.environ.get(f"{prefix}DEBUG_ON", "0") == "1",
        }
        return cls(**{**env, **overrides})

    # -- lifecycle ----------------------------------------------------------
    async def aclose(self) -> None:
        """Close the session, but only if we created it."""
        if not self._owns_session or self._session is None:
            return
        if self._backend == "httpx":
            await self._session.aclose()
        elif not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    # -- internal helpers ---------------------------------------------------
    async def _get_session(self):
        # User-supplied sessions are returned as-is. The default (owned) aiohttp
        # session is created lazily, and re-created if it was closed.
        if self._session is not None and not (
            self._owns_session and getattr(self._session, "closed", False)
        ):
            return self._session
        import aiohttp

        timeout = (
            aiohttp.ClientTimeout(total=self._timeout)
            if self._timeout is not None
            else None
        )
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _post(self, url: str, params: dict) -> dict:
        session = await self._get_session()
        try:
            if self._backend == "httpx":
                resp = await session.post(url, data=params)
                resp.raise_for_status()
                text = resp.text
            else:
                async with session.post(url, data=params) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
        except Exception as e:
            raise PayTRNetworkError(f"PayTR request to {url} failed: {e}") from e
        try:
            return json.loads(text)
        except (ValueError, TypeError) as e:
            raise PayTRNetworkError(
                f"PayTR returned a non-JSON response from {url}: {text[:200]!r}"
            ) from e

    @property
    def _test_flag(self) -> str:
        """``"1"``/``"0"`` form of ``test_mode`` for the PayTR params."""
        return "1" if self.test_mode else "0"

    @property
    def _debug_flag(self) -> str:
        """``"1"``/``"0"`` form of ``debug_on`` for the PayTR params."""
        return "1" if self.debug_on else "0"

    def _sign(self, builder, **kwargs) -> str:
        """Call a :mod:`._crypto` token builder with this client's signing keys."""
        return builder(
            merchant_key=self.merchant_key,
            merchant_salt=self.merchant_salt,
            **kwargs,
        )

    async def _post_checked(
        self,
        url: str,
        params: dict,
        *,
        scope: Scope,
        default: str | None = None,
        ok_statuses: tuple[str, ...] = ("success",),
    ) -> dict:
        """POST and raise unless ``status`` is one of ``ok_statuses``."""
        result = await self._post(url, params)
        if result.get("status") not in ok_statuses:
            raise self._api_error(scope, result, default)
        return result

    @staticmethod
    def _api_error(scope: Scope, result: dict, default: str | None = None) -> PayTRAPIError:
        code = result.get("err_no")
        code = str(code) if code is not None else None
        message = (
            result.get("err_msg")
            or result.get("reason")
            or describe(scope, code)
            or default
            or f"{scope} request failed"
        )
        return PayTRAPIError(message, code=code, scope=scope, payload=result)

    # -- callback verification (STEP 2) ------------------------------------
    def verify_callback(
        self, *, merchant_oid: str, status: str, total_amount: str, hash: str
    ) -> bool:
        """Verify the ``hash`` on an incoming callback POST. Always verify.

        Shared by the iFrame, link and direct-payment flows — PayTR signs every
        callback the same way (``oid + salt + status + total_amount``).
        """
        return _crypto.verify_callback(
            merchant_oid=merchant_oid,
            status=status,
            total_amount=total_amount,
            received_hash=hash,
            merchant_key=self.merchant_key,
            merchant_salt=self.merchant_salt,
        )
