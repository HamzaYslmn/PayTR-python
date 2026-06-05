"""Reporting APIs: transaction-detail, payment statement and payment-detail."""

from __future__ import annotations

from . import _crypto
from ._base import _BaseClient

TRANSACTION_DETAIL_URL = "https://www.paytr.com/rapor/islem-dokumu"
STATEMENT_URL = "https://www.paytr.com/rapor/odeme-dokumu"
PAYMENT_DETAIL_URL = "https://www.paytr.com/rapor/odeme-detayi"


class ReportingMixin(_BaseClient):
    """Date-range and single-day reports."""

    async def transaction_detail(self, *, start_date: str, end_date: str) -> list[dict]:
        """Transaction-detail report (``"YYYY-MM-DD hh:mm:ss"`` range).

        Returns ``[]`` when PayTR reports no transactions (``status == "failed"``).
        """
        result = await self._report_range(TRANSACTION_DETAIL_URL, start_date, end_date)
        if result is None:
            return []
        return result.get("returns") or result.get("data") or []

    async def payment_statement(self, *, start_date: str, end_date: str) -> dict:
        """Payment statement / summary report (``"YYYY-MM-DD"`` range).

        Returns ``{}`` when PayTR reports no data (``status == "failed"``).
        """
        result = await self._report_range(STATEMENT_URL, start_date, end_date)
        return result or {}

    async def payment_detail(self, date: str) -> dict:
        """Payment-detail report for a single day (``"YYYY-MM-DD"``).

        Returns ``{}`` when PayTR reports no data (``status == "failed"``).
        """
        token = self._sign(
            _crypto.report_date_token,
            merchant_id=self.merchant_id,
            date=date,
        )
        params = {"merchant_id": self.merchant_id, "date": date, "paytr_token": token}
        result = await self._post_report(PAYMENT_DETAIL_URL, params)
        return result or {}

    async def _report_range(self, url: str, start_date: str, end_date: str) -> dict | None:
        token = self._sign(
            _crypto.report_range_token,
            merchant_id=self.merchant_id,
            start_date=start_date,
            end_date=end_date,
        )
        params = {
            "merchant_id": self.merchant_id,
            "start_date": start_date,
            "end_date": end_date,
            "paytr_token": token,
        }
        return await self._post_report(url, params)

    async def _post_report(self, url: str, params: dict) -> dict | None:
        # Report endpoints signal "no data" with status == "failed" and share the
        # status-query error table for real errors.
        result = await self._post(url, params)
        status = result.get("status")
        if status == "failed":
            return None
        if status != "success":
            raise self._api_error("status", result)
        return result
