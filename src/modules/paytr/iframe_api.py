"""iFrame API (STEP 1 get-token, card + Havale/EFT) and the iFrame embed helpers."""

from __future__ import annotations

from decimal import Decimal

from . import _crypto
from ._base import BasketLine, PaymentType, _BaseClient, _minor_units, encode_basket

GET_TOKEN_URL = "https://www.paytr.com/odeme/api/get-token"
IFRAME_BASE_URL = "https://www.paytr.com/odeme/guvenli"


def iframe_url(token: str) -> str:
    """Return the ``src`` URL for the payment iFrame."""
    return f"{IFRAME_BASE_URL}/{token}"


def iframe_html(token: str, *, iframe_id: str = "paytriframe") -> str:
    """Return a ready-to-embed HTML snippet (iframe + auto-resizer)."""
    return (
        '<script src="https://www.paytr.com/js/iframeResizer.min.js"></script>\n'
        f'<iframe src="{IFRAME_BASE_URL}/{token}" id="{iframe_id}" '
        'frameborder="0" scrolling="no" style="width: 100%;"></iframe>\n'
        f"<script>iFrameResize({{}},'#{iframe_id}');</script>"
    )


class IframeMixin(_BaseClient):
    """STEP 1 ``get-token`` for the hosted payment iFrame."""

    async def create_iframe_token(
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
        currency: str = "TL",
        lang: str = "tr",
        no_installment: int | None = None,
        max_installment: int | None = None,
        timeout_limit: int | None = None,
        iframe_v2: bool = True,
        dark_mode: bool = False,
        payment_type: PaymentType = "card",
    ) -> dict:
        """Obtain an ``iframe_token`` to render the payment form (new design by default).

        ``payment_amount`` and basket prices are in *major units*. Set
        ``payment_type="eft"`` for the Havale/EFT (bank-transfer) iFrame, which
        signs a different field set; the default ``"card"`` is the standard
        credit-card iFrame. Returns ``{"status", "token", "merchant_oid",
        "payment_amount"}`` on success and raises :class:`PayTRAPIError` /
        :class:`PayTRNetworkError` otherwise.
        """
        currency = "TL" if currency == "TRY" else currency
        amount = str(_minor_units(payment_amount))
        basket = encode_basket(user_basket)
        test_mode = "1" if self.test_mode else "0"
        ni = str(self.default_no_installment if no_installment is None else no_installment)
        mi = str(self.default_max_installment if max_installment is None else max_installment)
        is_eft = payment_type == "eft"

        if is_eft:
            # Havale/EFT signs id+ip+oid+email+amount+payment_type+test (+salt).
            token = _crypto.eft_token(
                merchant_id=self.merchant_id,
                user_ip=user_ip,
                merchant_oid=merchant_oid,
                email=email,
                payment_amount=amount,
                payment_type="eft",
                test_mode=test_mode,
                merchant_key=self.merchant_key,
                merchant_salt=self.merchant_salt,
            )
        else:
            token = _crypto.iframe_token(
                merchant_id=self.merchant_id,
                user_ip=user_ip,
                merchant_oid=merchant_oid,
                email=email,
                payment_amount=amount,
                user_basket=basket,
                no_installment=ni,
                max_installment=mi,
                currency=currency,
                test_mode=test_mode,
                merchant_key=self.merchant_key,
                merchant_salt=self.merchant_salt,
            )

        params = {
            "merchant_id": self.merchant_id,
            "user_ip": user_ip,
            "merchant_oid": merchant_oid,
            "email": email,
            "payment_amount": amount,
            "paytr_token": token,
            "user_basket": basket,
            "debug_on": "1" if self.debug_on else "0",
            "no_installment": ni,
            "max_installment": mi,
            "user_name": user_name,
            "user_address": user_address,
            "user_phone": user_phone,
            "merchant_ok_url": merchant_ok_url,
            "merchant_fail_url": merchant_fail_url,
            "timeout_limit": str(
                self.default_timeout_limit if timeout_limit is None else timeout_limit
            ),
            "currency": currency,
            "test_mode": test_mode,
            "lang": lang,
        }
        if is_eft:
            params["payment_type"] = "eft"
        if iframe_v2:
            params["iframe_v2"] = "1"
            params["iframe_v2_dark"] = "1" if dark_mode else "0"

        result = await self._post(GET_TOKEN_URL, params)
        if result.get("status") != "success":
            raise self._api_error("payment", result, "get-token failed")

        return {
            "status": "success",
            "token": result["token"],
            "merchant_oid": merchant_oid,
            "payment_amount": int(amount),
        }

    # iFrame URL/HTML helpers (also importable as module-level functions)
    iframe_url = staticmethod(iframe_url)
    iframe_html = staticmethod(iframe_html)
