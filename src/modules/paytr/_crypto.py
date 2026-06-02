"""HMAC-SHA256 token / hash helpers for the PayTR APIs.

PayTR signs every server-to-server request (and signs its own callbacks) with an
HMAC-SHA256 digest, base64 encoded. Only the *order of the concatenated fields*
changes between endpoints, so there is one function per concatenation order.

``merchant_key`` is the HMAC secret; ``merchant_salt`` is mixed into the signed
string. Both accept ``str`` or ``bytes``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

Key = str | bytes


def _b(value: Key) -> bytes:
    return value if isinstance(value, bytes) else value.encode()


def _sign(merchant_key: Key, message: bytes) -> str:
    """Return ``base64(HMAC_SHA256(merchant_key, message))`` as ``str``."""
    return base64.b64encode(
        hmac.new(_b(merchant_key), message, hashlib.sha256).digest()
    ).decode()


def iframe_token(
    *,
    merchant_id: str,
    user_ip: str,
    merchant_oid: str,
    email: str,
    payment_amount: str,
    user_basket: str,
    no_installment: str,
    max_installment: str,
    currency: str,
    test_mode: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """get-token: ``id+ip+oid+email+amount+basket+no_inst+max_inst+currency+test`` (+salt)."""
    hash_str = (
        f"{merchant_id}{user_ip}{merchant_oid}{email}{payment_amount}"
        f"{user_basket}{no_installment}{max_installment}{currency}{test_mode}"
    )
    return _sign(merchant_key, hash_str.encode() + _b(merchant_salt))


def eft_token(
    *,
    merchant_id: str,
    user_ip: str,
    merchant_oid: str,
    email: str,
    payment_amount: str,
    payment_type: str,
    test_mode: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Havale/EFT get-token: ``id+ip+oid+email+amount+payment_type+test`` (+salt)."""
    hash_str = (
        f"{merchant_id}{user_ip}{merchant_oid}{email}"
        f"{payment_amount}{payment_type}{test_mode}"
    )
    return _sign(merchant_key, hash_str.encode() + _b(merchant_salt))


def callback_hash(
    *,
    merchant_oid: str,
    status: str,
    total_amount: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Callback: ``oid + salt + status + total_amount``."""
    hash_str = f"{merchant_oid}{_b(merchant_salt).decode()}{status}{total_amount}"
    return _sign(merchant_key, hash_str.encode())


def verify_callback(
    *,
    merchant_oid: str,
    status: str,
    total_amount: str,
    received_hash: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> bool:
    """Constant-time check that a callback ``hash`` is authentic."""
    expected = callback_hash(
        merchant_oid=merchant_oid,
        status=status,
        total_amount=total_amount,
        merchant_key=merchant_key,
        merchant_salt=merchant_salt,
    )
    return hmac.compare_digest(expected, received_hash)


def refund_token(
    *,
    merchant_id: str,
    merchant_oid: str,
    return_amount: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Refund: ``id + oid + return_amount + salt``."""
    hash_str = f"{merchant_id}{merchant_oid}{return_amount}{_b(merchant_salt).decode()}"
    return _sign(merchant_key, hash_str.encode())


def status_token(
    *,
    merchant_id: str,
    merchant_oid: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Status query: ``id + oid + salt``."""
    hash_str = f"{merchant_id}{merchant_oid}{_b(merchant_salt).decode()}"
    return _sign(merchant_key, hash_str.encode())


def report_range_token(
    *,
    merchant_id: str,
    start_date: str,
    end_date: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Range reports (transaction-detail, statement): ``id + start + end + salt``."""
    hash_str = f"{merchant_id}{start_date}{end_date}{_b(merchant_salt).decode()}"
    return _sign(merchant_key, hash_str.encode())


def report_date_token(
    *,
    merchant_id: str,
    date: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Single-date report (payment-detail): ``id + date + salt``."""
    hash_str = f"{merchant_id}{date}{_b(merchant_salt).decode()}"
    return _sign(merchant_key, hash_str.encode())


def link_create_token(
    *,
    name: str,
    price: str,
    currency: str,
    max_installment: str,
    link_type: str,
    lang: str,
    conditional: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Link create: ``name+price+currency+max_inst+link_type+lang+conditional`` (+salt).

    ``conditional`` is ``min_count`` for ``link_type="product"`` or ``email`` for
    ``"collection"`` — the caller picks which; this builder only fixes the order.
    """
    hash_str = f"{name}{price}{currency}{max_installment}{link_type}{lang}{conditional}"
    return _sign(merchant_key, hash_str.encode() + _b(merchant_salt))


def link_delete_token(
    *,
    link_id: str,
    merchant_id: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Link delete: ``id + merchant_id`` (+salt)."""
    hash_str = f"{link_id}{merchant_id}"
    return _sign(merchant_key, hash_str.encode() + _b(merchant_salt))


def bin_token(
    *,
    bin_number: str,
    merchant_id: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """BIN lookup: ``bin_number + merchant_id`` (+salt)."""
    hash_str = f"{bin_number}{merchant_id}"
    return _sign(merchant_key, hash_str.encode() + _b(merchant_salt))


def installment_rates_token(
    *,
    merchant_id: str,
    request_id: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Installment rates: ``merchant_id + request_id`` (+salt)."""
    hash_str = f"{merchant_id}{request_id}"
    return _sign(merchant_key, hash_str.encode() + _b(merchant_salt))


def card_list_token(
    *,
    utoken: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Stored-card list: ``utoken + salt``.

    Salt is the trailing segment of the signed message (like ``status_token``),
    *not* a separately appended secret — don't append it twice.
    """
    hash_str = f"{utoken}{_b(merchant_salt).decode()}"
    return _sign(merchant_key, hash_str.encode())


def card_delete_token(
    *,
    ctoken: str,
    utoken: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Stored-card delete: ``ctoken + utoken + salt`` (salt inline, as in list)."""
    hash_str = f"{ctoken}{utoken}{_b(merchant_salt).decode()}"
    return _sign(merchant_key, hash_str.encode())


def direct_payment_token(
    *,
    merchant_id: str,
    user_ip: str,
    merchant_oid: str,
    email: str,
    payment_amount: str,
    payment_type: str,
    installment_count: str,
    currency: str,
    test_mode: str,
    non_3d: str,
    merchant_key: Key,
    merchant_salt: Key,
) -> str:
    """Direct / recurring payment: ``id+ip+oid+email+amount+payment_type
    +installment_count+currency+test+non_3d`` (+salt).

    ``store_card``, ``recurring_payment``, ``utoken``, ``ctoken`` and ``cvv`` are
    *not* part of the signature.
    """
    hash_str = (
        f"{merchant_id}{user_ip}{merchant_oid}{email}{payment_amount}"
        f"{payment_type}{installment_count}{currency}{test_mode}{non_3d}"
    )
    return _sign(merchant_key, hash_str.encode() + _b(merchant_salt))
