"""Link API: create / delete payment links and verify their callbacks."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from . import _crypto
from ._base import _BaseClient, _minor_units
from .exceptions import PayTRConfigError

LINK_CREATE_URL = "https://www.paytr.com/odeme/api/link/create"
LINK_DELETE_URL = "https://www.paytr.com/odeme/api/link/delete"


class LinkMixin(_BaseClient):
    """Payment links (hosted PayTR pay-by-link)."""

    async def create_payment_link(
        self,
        *,
        name: str,
        price: str | float | Decimal,
        currency: str = "TL",
        max_installment: int = 0,
        link_type: Literal["product", "collection"] = "product",
        lang: str = "tr",
        min_count: int | None = None,
        email: str | None = None,
        max_count: int | None = None,
        expiry_date: str | None = None,
        callback_link: str | None = None,
        callback_id: str | None = None,
        get_qr: bool = False,
        pft: int | None = None,
    ) -> dict:
        """Create a PayTR payment link. ``price`` is in *major units* (e.g. ``14.45``).

        ``link_type="product"`` requires ``min_count`` (minimum quantity);
        ``"collection"`` (invoice / tahsilat) requires ``email``. On success
        returns the PayTR ``{"status", "id", "link", "qr"?}`` (``qr`` only when
        ``get_qr=True``); the link's payment result later arrives at
        ``callback_link`` as a standard callback (verify with
        :meth:`verify_link_callback`).
        """
        currency = "TL" if currency == "TRY" else currency
        if link_type == "product":
            if min_count is None:
                raise PayTRConfigError("link_type='product' requires min_count")
            conditional = str(min_count)
        else:
            if not email:
                raise PayTRConfigError("link_type='collection' requires email")
            conditional = email

        amount = str(_minor_units(price))
        mi = str(max_installment)
        token = _crypto.link_create_token(
            name=name,
            price=amount,
            currency=currency,
            max_installment=mi,
            link_type=link_type,
            lang=lang,
            conditional=conditional,
            merchant_key=self.merchant_key,
            merchant_salt=self.merchant_salt,
        )
        params = {
            "merchant_id": self.merchant_id,
            "name": name,
            "price": amount,
            "currency": currency,
            "max_installment": mi,
            "link_type": link_type,
            "lang": lang,
            "paytr_token": token,
            "get_qr": "1" if get_qr else "0",
            "debug_on": "1" if self.debug_on else "0",
        }
        if link_type == "product":
            params["min_count"] = str(min_count)
            if max_count is not None:
                params["max_count"] = str(max_count)
        else:
            params["email"] = email  # type: ignore[assignment]
        if expiry_date is not None:
            params["expiry_date"] = expiry_date
        if callback_link is not None:
            params["callback_link"] = callback_link
        if callback_id is not None:
            params["callback_id"] = callback_id
        if pft is not None:
            params["pft"] = str(pft)

        result = await self._post(LINK_CREATE_URL, params)
        if result.get("status") != "success":
            raise self._api_error("link", result, "create link failed")
        return result

    async def delete_payment_link(self, link_id: str) -> dict:
        """Delete a payment link by its PayTR ``id`` (from :meth:`create_payment_link`)."""
        token = _crypto.link_delete_token(
            link_id=link_id,
            merchant_id=self.merchant_id,
            merchant_key=self.merchant_key,
            merchant_salt=self.merchant_salt,
        )
        params = {
            "merchant_id": self.merchant_id,
            "id": link_id,
            "paytr_token": token,
            "debug_on": "1" if self.debug_on else "0",
        }
        result = await self._post(LINK_DELETE_URL, params)
        if result.get("status") != "success":
            raise self._api_error("link", result, "delete link failed")
        return result

    def verify_link_callback(
        self,
        *,
        merchant_oid: str,
        status: str,
        total_amount: str,
        hash: str,
        callback_id: str | None = None,
    ) -> bool:
        """Verify a payment-link callback.

        Identical to :meth:`verify_callback` (signs
        ``oid + salt + status + total_amount``). ``callback_id`` is echoed back
        by PayTR for your own correlation but is *not* part of the hash, so it is
        accepted and ignored here.
        """
        return self.verify_callback(
            merchant_oid=merchant_oid,
            status=status,
            total_amount=total_amount,
            hash=hash,
        )
