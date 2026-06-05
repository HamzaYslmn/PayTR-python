"""Status query API: look up the current state of an order."""

from __future__ import annotations

from . import _crypto
from ._base import _BaseClient

STATUS_URL = "https://www.paytr.com/odeme/durum-sorgu"


class StatusMixin(_BaseClient):
    """Order status queries."""

    async def status(self, merchant_oid: str) -> dict:
        """Query the current status of an order (amount, refunds, card info, ...)."""
        token = self._sign(
            _crypto.status_token,
            merchant_id=self.merchant_id,
            merchant_oid=merchant_oid,
        )
        params = {
            "merchant_id": self.merchant_id,
            "merchant_oid": merchant_oid,
            "paytr_token": token,
        }
        return await self._post_checked(STATUS_URL, params, scope="status")
