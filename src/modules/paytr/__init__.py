"""paytr — a small async client + ready-to-use FastAPI routes for the PayTR APIs.

Covers most of the PayTR surface: iFrame get-token (card + Havale/EFT, new
design), callback verification, refund, status query, the transaction-detail /
statement / payment-detail reports, payment links, BIN lookup, installment-rate
query, stored-card management and direct/recurring payment — plus the official
error-code tables. The iFrame flow is the easy default; the rest are backend
operations called straight from :class:`PayTRClient`.

Two ways to use it:

1. The client (framework-agnostic)::

       from paytr import PayTRClient, iframe_html
       client = PayTRClient(merchant_id=..., merchant_key=..., merchant_salt=...)
       result = await client.create_iframe_token(...)
       html = iframe_html(result["token"])

2. Ready-to-use FastAPI routes::

       from paytr import PayTRClient
       from paytr.fastapi import include_paytr_routes
       include_paytr_routes(app, client, on_payment=handler)

``paytr.fastapi`` requires the ``[fastapi]`` extra; importing ``paytr`` itself
does not pull in FastAPI.
"""

from __future__ import annotations

from . import _crypto as crypto
from . import errors
from .client import PayTRClient, encode_basket, iframe_html, iframe_url
from .errors import describe
from ._log import logger, setup_logging
from .exceptions import (
    PayTRAPIError,
    PayTRConfigError,
    PayTRError,
    PayTRNetworkError,
)

__version__ = "0.1.1"

__all__ = [
    "PayTRClient",
    "encode_basket",
    "iframe_url",
    "iframe_html",
    "errors",
    "describe",
    "logger",
    "setup_logging",
    "PayTRError",
    "PayTRConfigError",
    "PayTRNetworkError",
    "PayTRAPIError",
    "crypto",
    "__version__",
]
