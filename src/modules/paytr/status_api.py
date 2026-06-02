"""Status query API: look up the current state of an order."""

from __future__ import annotations

from . import _crypto
from ._base import _BaseClient

STATUS_URL = "https://www.paytr.com/odeme/durum-sorgu"


class StatusMixin(_BaseClient):
    """Order status queries."""

    async def status(self, merchant_oid: str) -> dict:
        """Query the current status of an order (amount, refunds, card info, ...)."""
        token = _crypto.status_token(
            merchant_id=self.merchant_id,
            merchant_oid=merchant_oid,
            merchant_key=self.merchant_key,
            merchant_salt=self.merchant_salt,
        )
        params = {
            "merchant_id": self.merchant_id,
            "merchant_oid": merchant_oid,
            "paytr_token": token,
        }
        result = await self._post(STATUS_URL, params)
        if result.get("status") != "success":
            raise self._api_error("status", result, "status query failed")
        return result
