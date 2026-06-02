"""Exception types raised by the PayTR client."""

from __future__ import annotations


class PayTRError(Exception):
    """Base class for all PayTR errors."""


class PayTRConfigError(PayTRError):
    """Raised when the client is misconfigured (missing credentials, etc.)."""


class PayTRNetworkError(PayTRError):
    """Raised when the PayTR API cannot be reached or returns invalid data."""


class PayTRAPIError(PayTRError):
    """Raised when PayTR responds with ``status != "success"``.

    Attributes:
        message: Human-readable explanation (PayTR ``err_msg``/``reason`` or a
            message resolved from the error-code tables).
        code: The raw PayTR error code (``err_no``), when provided.
        scope: Which error table ``code`` belongs to (``payment``/``refund``/``status``).
        payload: The full decoded response from PayTR, when available.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        scope: str | None = None,
        payload: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.reason = message  # backwards-compatible alias
        self.code = code
        self.scope = scope
        self.payload = payload or {}
