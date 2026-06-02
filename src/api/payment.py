"""Mounts the ready-to-use PayTR routes from the library under /paytr.

This is all the wiring an app needs — the endpoints themselves live in
``paytr.fastapi``. Just supply a configured client and a payment handler.
"""

import logging

from fastapi import APIRouter  # noqa: F401 — router auto-discovery marker

from paytr._client import client
from paytr.fastapi import CallbackData, create_paytr_router

log = logging.getLogger("paytr")


async def on_payment(data: CallbackData) -> None:
    """Business logic for a verified callback. Idempotent per merchant_oid."""
    if data.is_success:
        log.info("PAID   oid=%s amount=%s", data.merchant_oid, data.total_amount)
    else:
        log.info(
            "FAILED oid=%s code=%s msg=%s",
            data.merchant_oid,
            data.failed_reason_code,
            data.error_message,
        )


router = create_paytr_router(client, on_payment=on_payment)
