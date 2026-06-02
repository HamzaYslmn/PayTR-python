"""``PayTRClient`` — the async client composed from the per-API mixins.

This module assembles the full client from one mixin per PayTR API, each living
in its own ``*_api.py`` module so no single file grows unwieldy:

* :mod:`paytr.iframe_api` — iFrame get-token (card + Havale/EFT) + embed helpers
* :mod:`paytr.link_api` — payment links
* :mod:`paytr.refund_api` — refunds
* :mod:`paytr.status_api` — order status query
* :mod:`paytr.reporting_api` — transaction / statement / payment-detail reports
* :mod:`paytr.direct_api` — direct & recurring payment, stored cards, BIN /
  installment queries

Shared construction, the HTTP lifecycle, signing-key access, callback
verification, error mapping and the amount/basket encoders live in
:mod:`paytr._base`. The iFrame flow is the easy default; everything else is a
backend operation called straight from the client.

The client works with plain Python values (no request/response model classes) so
callers — FastAPI routes, scripts, anything — define their own validation.

Amount gotcha: ``create_iframe_token`` and link ``price`` take *minor-unit
integers* (the library x100s major units for you), while ``refund`` and
``direct_payment`` take a *major-unit string* like ``"34.56"``. They are signed
differently — pick the right method.
"""

from __future__ import annotations

# Re-exported so existing imports (and tests) keep working unchanged.
from ._base import (
    BasketLine,
    PaymentType,
    _minor_units,
    encode_basket,
)
from .direct_api import DirectMixin
from .iframe_api import IframeMixin, iframe_html, iframe_url
from .link_api import LinkMixin
from .refund_api import RefundMixin
from .reporting_api import ReportingMixin
from .status_api import StatusMixin

__all__ = [
    "PayTRClient",
    "BasketLine",
    "PaymentType",
    "encode_basket",
    "iframe_url",
    "iframe_html",
]


class PayTRClient(
    IframeMixin,
    LinkMixin,
    RefundMixin,
    StatusMixin,
    ReportingMixin,
    DirectMixin,
):
    """Async client for the PayTR APIs.

    Credentials live on the client; per-request data is passed to each method.
    Reuse one instance for connection pooling and close it on shutdown
    (``await client.aclose()``), or use it as an async context manager.

    Methods are grouped by API in the mixins this class composes — see the
    module docstring. Construction and the HTTP-session options are documented
    on :class:`paytr._base._BaseClient`.
    """
