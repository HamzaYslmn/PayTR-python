"""Direct API: server-side card charge, stored cards, BIN and installment queries.

These are the non-iFrame Direct API endpoints. ``direct_payment`` charges a card
without the hosted form (so it carries higher PCI scope and needs Non3D for
recurring); the rest are read-only lookups and stored-card management.
"""

from __future__ import annotations

from decimal import Decimal

from . import _crypto
from ._base import (
    BasketLine,
    _BaseClient,
    _money,
    _normalize_currency,
    encode_basket,
)
from .exceptions import PayTRConfigError

BIN_DETAIL_URL = "https://www.paytr.com/odeme/api/bin-detail"
INSTALLMENT_RATES_URL = "https://www.paytr.com/odeme/taksit-oranlari"
CARD_LIST_URL = "https://www.paytr.com/odeme/capi/list"
CARD_DELETE_URL = "https://www.paytr.com/odeme/capi/delete"
DIRECT_PAYMENT_URL = "https://www.paytr.com/odeme"


class DirectMixin(_BaseClient):
    """Direct-API payment plus its BIN / installment / stored-card services."""

    # -- lookups (BIN, installment) ----------------------------------------
    async def bin_detail(self, bin_number: str) -> dict:
        """Look up card brand / bank / 3D eligibility for a BIN (first 6-8 digits)."""
        if not (bin_number.isdigit() and 6 <= len(bin_number) <= 8):
            raise PayTRConfigError("bin_number must be 6 to 8 digits")
        token = self._sign(
            _crypto.bin_token,
            bin_number=bin_number,
            merchant_id=self.merchant_id,
        )
        params = {
            "merchant_id": self.merchant_id,
            "bin_number": bin_number,
            "paytr_token": token,
        }
        return await self._post_checked(BIN_DETAIL_URL, params, scope="bin")

    async def installment_rates(self, request_id: str) -> dict:
        """Query the merchant's installment commission rates. ``request_id`` is a
        unique id you choose (max 32 chars), echoed back in the response."""
        if len(request_id) > 32:
            raise PayTRConfigError("request_id must be at most 32 characters")
        token = self._sign(
            _crypto.installment_rates_token,
            merchant_id=self.merchant_id,
            request_id=request_id,
        )
        params = {
            "merchant_id": self.merchant_id,
            "request_id": request_id,
            "paytr_token": token,
        }
        return await self._post_checked(
            INSTALLMENT_RATES_URL, params, scope="installment"
        )

    # -- stored cards (recurring) ------------------------------------------
    async def list_cards(self, utoken: str) -> dict:
        """List a user's stored cards by their ``utoken`` (returned in the callback
        of a ``store_card`` payment). Each card carries its ``ctoken`` for charging."""
        token = self._sign(_crypto.card_list_token, utoken=utoken)
        params = {
            "merchant_id": self.merchant_id,
            "utoken": utoken,
            "paytr_token": token,
        }
        return await self._post_checked(
            CARD_LIST_URL, params, scope="card", default="card list failed"
        )

    async def delete_card(self, *, utoken: str, ctoken: str) -> dict:
        """Delete one stored card (``ctoken``) from a user (``utoken``)."""
        token = self._sign(
            _crypto.card_delete_token,
            ctoken=ctoken,
            utoken=utoken,
        )
        params = {
            "merchant_id": self.merchant_id,
            "utoken": utoken,
            "ctoken": ctoken,
            "paytr_token": token,
        }
        return await self._post_checked(
            CARD_DELETE_URL, params, scope="card", default="card delete failed"
        )

    # -- direct / recurring payment ----------------------------------------
    async def direct_payment(
        self,
        *,
        merchant_oid: str,
        email: str,
        payment_amount: str | float | Decimal,
        user_ip: str,
        user_name: str,
        user_address: str,
        user_phone: str,
        user_basket: list[BasketLine],
        merchant_ok_url: str,
        merchant_fail_url: str,
        payment_type: str = "card",
        installment_count: int = 0,
        currency: str = "TL",
        non_3d: bool = False,
        store_card: bool = False,
        recurring: bool = False,
        utoken: str | None = None,
        ctoken: str | None = None,
        cvv: str | None = None,
    ) -> dict:
        """Charge a card server-side via the Direct API (no iFrame).

        ``payment_amount`` is in *major units* as a ``"100.99"``-style string —
        unlike the iFrame, which uses minor-unit integers. Set ``store_card=True``
        to save the card (the ``utoken`` comes back in the callback), or pass
        ``recurring=True`` with a saved ``utoken``/``ctoken`` to charge it again.
        Recurring/stored-card charges run Non3D, so ``non_3d`` is forced on for
        ``recurring=True`` (your store must have Non3D enabled).

        Returns PayTR's immediate ``{"status", ...}`` where ``status`` is
        ``"success"``, ``"wait_callback"`` (final result arrives at your callback
        URL — verify with :meth:`verify_callback`) or ``"failed"`` (raises).
        """
        currency = _normalize_currency(currency)
        amount = _money(payment_amount)
        ic = str(installment_count)
        test_mode = self._test_flag
        non_3d_flag = "1" if (non_3d or recurring) else "0"

        token = self._sign(
            _crypto.direct_payment_token,
            merchant_id=self.merchant_id,
            user_ip=user_ip,
            merchant_oid=merchant_oid,
            email=email,
            payment_amount=amount,
            payment_type=payment_type,
            installment_count=ic,
            currency=currency,
            test_mode=test_mode,
            non_3d=non_3d_flag,
        )
        params = {
            "merchant_id": self.merchant_id,
            "user_ip": user_ip,
            "merchant_oid": merchant_oid,
            "email": email,
            "payment_amount": amount,
            "payment_type": payment_type,
            "installment_count": ic,
            "currency": currency,
            "test_mode": test_mode,
            "non_3d": non_3d_flag,
            "paytr_token": token,
            "user_name": user_name,
            "user_address": user_address,
            "user_phone": user_phone,
            "user_basket": encode_basket(user_basket),
            "merchant_ok_url": merchant_ok_url,
            "merchant_fail_url": merchant_fail_url,
            "debug_on": self._debug_flag,
        }
        # Card-storage / recurring fields are deliberately *not* part of the hash.
        if store_card:
            params["store_card"] = "1"
        if recurring:
            params["recurring_payment"] = "1"
        if utoken is not None:
            params["utoken"] = utoken
        if ctoken is not None:
            params["ctoken"] = ctoken
        if cvv is not None:
            params["cvv"] = cvv

        return await self._post_checked(
            DIRECT_PAYMENT_URL,
            params,
            scope="direct",
            ok_statuses=("success", "wait_callback"),
        )
