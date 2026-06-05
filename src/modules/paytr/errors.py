"""PayTR error-code tables and lookup.

Source: https://dev.paytr.com/en/hata-kodlari

Scopes exposed: ``payment`` (callback ``failed_reason_code`` / payment
denial), ``refund`` (refund API ``err_no``), ``status`` (status-query
``err_no``), and ``transfer`` / ``platform`` (marketplace platform transfer ``err_no``).
Use :func:`describe` to turn a raw code into a human message.

The link, BIN, installment, stored-card and direct-payment endpoints return
their failure reason as free text (``reason`` / ``err_msg``), not numeric codes,
so :class:`~paytr.exceptions.PayTRAPIError` surfaces PayTR's own message for
them; :func:`describe` falls back to a generic message for any scope without a
table.
"""

from __future__ import annotations

from typing import Literal

# A scope names one error table below (the keys of ``_TABLES``). It is a typing
# aid only — :func:`describe` still accepts any string and degrades gracefully.
Scope = Literal[
    "payment",
    "refund",
    "status",
    "transfer",
    "platform",
    "link",
    "bin",
    "installment",
    "card",
    "direct",
]

# MARK: Error Mappings

# Callback failed_reason_code / payment-denial codes.
PAYMENT_ERRORS: dict[str, str] = {
    "0": "Declined by bank — see failed_reason_msg (e.g. insufficient limit/balance)",
    "1": "Authentication not performed; customer did not enter the phone number",
    "2": "Authentication failed; customer entered the wrong SMS password",
    "3": "Not approved after security checks",
    "4": "Transfer/EFT payment could not be detected",
    "5": "Insufficient transfer/EFT amount sent",
    "6": "Customer abandoned the payment or it timed out",
    "7": "Notification not received; please wait for the check on your previous notification to complete",
    "8": "Installment not supported by this card",
    "9": "Merchant not authorised to process this card",
    "10": "3D Secure required for this transaction",
    "11": "Security alert; possible fraud — review the customer",
    "99": "Technical integration error",
}

# Refund API err_no codes.
REFUND_ERRORS: dict[str, str] = {
    "000": "Cannot process refund right now (locked during payment processing)",
    "001": "Invalid request or store inactive (missing merchant_id)",
    "002": "merchant_oid not provided",
    "003": "return_amount not provided",
    "004": "paytr_token missing or incorrect",
    "005": "No successful payment found for this order",
    "007": "Payment notification not yet completed for this order",
    "008": "Refunds unavailable for this payment method",
    "009": "Refund exceeds the remaining transaction amount",
    "010": "Insufficient account balance for the refund",
    "011": "Cannot refund transactions older than one year",
    "012": "Platform commission cannot be less than zero",
}

# Status-query err_no codes.
STATUS_ERRORS: dict[str, str] = {
    "001": "Invalid request or store inactive (missing merchant_id)",
    "002": "merchant_oid not provided",
    "003": "paytr_token missing or incorrect",
    "004": "Transaction not found or successful payment not found for this merchant_oid",
}

# Marketplace platform transfer request err_no codes.
TRANSFER_ERRORS: dict[str, str] = {
    "001": "Invalid request or store inactive (missing merchant_id)",
    "002": "Not authorized for this service (merchant type is not marketplace)",
    "003": "Invalid or missing trans_id",
    "004": "paytr_token not sent or invalid",
    "005": "Invalid or missing merchant_oid",
    "006": "No successful payment found with this merchant_oid",
    "007": "merchant_oid found but payment notification is not yet completed",
    "008": "Transfer cannot be made before value date passes",
    "009": "trans_id must be unique; this trans_id has been used before",
    "010": "Total transfer amount cannot exceed the remaining balance",
    "012": "Platform commission cannot be less than zero",
    "091": "transfer_iban failed IBAN validation",
    "092": "transfer_iban must start with TR, contain no spaces or hyphens, and be 26 characters long",
    "095": "submerchant_amount cannot be less than zero",
    "096": "trans_id must be alphanumeric and contain no special characters",
    "097": "transfer_iban is required",
    "098": "transfer_name is required",
    "099": "total_amount must be numeric and greater than zero",
    "100": "transfer_name must contain a space between first and last name",
    "101": "First and last name in transfer_name must be at least 2 characters long",
    "201": "paytr_token not sent or invalid",
    "202": "trans_id must be alphanumeric and contain no special characters",
    "203": "trans_id must be unique; this trans_id has been used before",
    "204": "trans_info is longer than allowed; try again with fewer records",
    "205": "trans_info must contain between 2 and 2000 transactions",
    "206": "trans_info is not a valid JSON string",
    "301": "paytr_token not sent or invalid",
    "302": "trans_id must be alphanumeric and contain no special characters",
    "303": "trans_id must be unique; this trans_id has been used before",
    "305": "merchant_oids must contain between minimum and maximum allowed transactions",
    "306": "merchant_oids is not a valid JSON string",
    "BLK": "merchant_oid transaction is blocked; contact us for detailed information",
}

# MARK: Table Mapping and Lookup

# Reason-style scopes (link, bin, installment, card, direct) have no numeric
# tables — ``describe``'s ``.get(scope, {})`` default covers them.
_TABLES: dict[Scope, dict[str, str]] = {
    "payment": PAYMENT_ERRORS,
    "refund": REFUND_ERRORS,
    "status": STATUS_ERRORS,
    "transfer": TRANSFER_ERRORS,
    "platform": TRANSFER_ERRORS,
}


def describe(scope: Scope, code: str | int | None) -> str:
    """Human-readable message for an error ``code`` within a ``scope``.

    ``scope`` is one of ``"payment"``, ``"refund"``, ``"status"``,
    ``"transfer"``/``"platform"``, or a reason-style scope (``"link"``, ``"bin"``,
    ``"installment"``, ``"card"``, ``"direct"``). Returns an empty string for
    ``None`` and a generic message for unknown codes.
    """
    if code is None:
        return ""
    return _TABLES.get(scope, {}).get(
        str(code), f"Unknown {scope} error (code {code})"
    )
