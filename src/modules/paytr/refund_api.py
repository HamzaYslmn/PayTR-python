"""Refund API: refund all or part of an order."""

from __future__ import annotations

from decimal import Decimal

from . import _crypto
from ._base import _BaseClient, _money

REFUND_URL = "https://www.paytr.com/odeme/iade"


class RefundMixin(_BaseClient):
    """Refunds (full or partial)."""

    async def refund(
        self,
        *,
        merchant_oid: str,
        return_amount: str | float | Decimal,
        reference_no: str | None = None,
    ) -> dict:
        """Refund all or part of an order. ``return_amount`` is in major units."""
        amount = _money(return_amount)
        token = _crypto.refund_token(
            merchant_id=self.merchant_id,
            merchant_oid=merchant_oid,
            return_amount=amount,
            merchant_key=self.merchant_key,
            merchant_salt=self.merchant_salt,
        )
        params = {
            "merchant_id": self.merchant_id,
            "merchant_oid": merchant_oid,
            "return_amount": amount,
            "paytr_token": token,
        }
        if reference_no:
            params["reference_no"] = reference_no

        result = await self._post(REFUND_URL, params)
        if result.get("status") != "success":
            raise self._api_error("refund", result, "refund failed")
        return result
