"""Tests for paytr.

Hash tests recompute the expected token independently (mirroring the PayTR docs'
sample code), so a regression in any concatenation order is caught immediately.
Router tests use FastAPI's TestClient and never hit the network (callback
verification + validation are local).
"""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from paytr import PayTRClient, crypto, describe, encode_basket, iframe_html, iframe_url
from paytr._base import _minor_units, _normalize_currency

MERCHANT_ID = "123456"
MERCHANT_KEY = b"SECRETKEY12345"
MERCHANT_SALT = b"SALTSALTSALT12"
SALT_S = MERCHANT_SALT.decode()


def _ref(message: bytes) -> str:
    return base64.b64encode(
        hmac.new(MERCHANT_KEY, message, hashlib.sha256).digest()
    ).decode()


def _client() -> PayTRClient:
    return PayTRClient(
        merchant_id=MERCHANT_ID, merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT
    )


# --- basket / amount --------------------------------------------------------
def test_encode_basket_matches_paytr_format():
    encoded = encode_basket([("Item 1", "18.00", 1), ("Item 2", 33.25, 2)])
    assert base64.b64decode(encoded).decode() == '[["Item 1", "18.00", 1], ["Item 2", "33.25", 2]]'


def test_minor_units():
    assert _minor_units("34.56") == 3456
    assert _minor_units(34.56) == 3456
    assert _minor_units("0.01") == 1


def test_normalize_currency():
    # "TRY" is the ISO alias PayTR wants spelled "TL"; everything else passes through.
    assert _normalize_currency("TRY") == "TL"
    assert _normalize_currency("USD") == "USD"
    assert _normalize_currency("TL") == "TL"


# --- token / hash builders --------------------------------------------------
def test_iframe_token_hash():
    basket = encode_basket([("X", "34.56", 1)])
    token = crypto.iframe_token(
        merchant_id=MERCHANT_ID, user_ip="1.2.3.4", merchant_oid="ORDER1",
        email="a@b.com", payment_amount="3456", user_basket=basket,
        no_installment="0", max_installment="0", currency="TL", test_mode="1",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"{MERCHANT_ID}1.2.3.4ORDER1a@b.com3456{basket}00TL1".encode() + MERCHANT_SALT)


def test_eft_token_hash():
    token = crypto.eft_token(
        merchant_id=MERCHANT_ID, user_ip="1.2.3.4", merchant_oid="ORDER1",
        email="a@b.com", payment_amount="3456", payment_type="eft", test_mode="1",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"{MERCHANT_ID}1.2.3.4ORDER1a@b.com3456eft1".encode() + MERCHANT_SALT)


def test_callback_hash_roundtrip_and_tamper():
    good = _ref(f"ORDER1{SALT_S}success3456".encode())
    assert crypto.verify_callback(
        merchant_oid="ORDER1", status="success", total_amount="3456",
        received_hash=good, merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert not crypto.verify_callback(
        merchant_oid="ORDER1", status="success", total_amount="9999",
        received_hash=good, merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )


def test_refund_token_hash():
    token = crypto.refund_token(
        merchant_id=MERCHANT_ID, merchant_oid="ORDER1", return_amount="11.90",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"{MERCHANT_ID}ORDER111.90{SALT_S}".encode())


def test_status_token_hash():
    token = crypto.status_token(
        merchant_id=MERCHANT_ID, merchant_oid="ORDER1",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"{MERCHANT_ID}ORDER1{SALT_S}".encode())


def test_report_range_token_hash():
    token = crypto.report_range_token(
        merchant_id=MERCHANT_ID, start_date="2021-02-02 00:00:00",
        end_date="2021-02-04 23:59:59", merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"{MERCHANT_ID}2021-02-02 00:00:002021-02-04 23:59:59{SALT_S}".encode())


def test_report_date_token_hash():
    token = crypto.report_date_token(
        merchant_id=MERCHANT_ID, date="2021-07-01",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"{MERCHANT_ID}2021-07-01{SALT_S}".encode())


def test_link_create_token_hash():
    # product: conditional field is min_count
    product = crypto.link_create_token(
        name="Shirt", price="1445", currency="TL", max_installment="0",
        link_type="product", lang="tr", conditional="1",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert product == _ref(f"Shirt1445TL0producttr1".encode() + MERCHANT_SALT)
    # collection: conditional field is email
    collection = crypto.link_create_token(
        name="Invoice", price="5000", currency="TL", max_installment="0",
        link_type="collection", lang="tr", conditional="a@b.com",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert collection == _ref(f"Invoice5000TL0collectiontra@b.com".encode() + MERCHANT_SALT)


def test_link_delete_token_hash():
    token = crypto.link_delete_token(
        link_id="NB2Zlz3", merchant_id=MERCHANT_ID,
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"NB2Zlz3{MERCHANT_ID}".encode() + MERCHANT_SALT)


def test_bin_token_hash():
    token = crypto.bin_token(
        bin_number="435508", merchant_id=MERCHANT_ID,
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"435508{MERCHANT_ID}".encode() + MERCHANT_SALT)


def test_installment_rates_token_hash():
    token = crypto.installment_rates_token(
        merchant_id=MERCHANT_ID, request_id="REQ1",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"{MERCHANT_ID}REQ1".encode() + MERCHANT_SALT)


def test_card_list_token_hash():
    # salt is folded into the message, not appended as a separate secret.
    token = crypto.card_list_token(
        utoken="UT123", merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"UT123{SALT_S}".encode())


def test_card_delete_token_hash():
    token = crypto.card_delete_token(
        ctoken="CT9", utoken="UT123",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"CT9UT123{SALT_S}".encode())


def test_direct_payment_token_hash():
    token = crypto.direct_payment_token(
        merchant_id=MERCHANT_ID, user_ip="1.2.3.4", merchant_oid="ORDER1",
        email="a@b.com", payment_amount="100.99", payment_type="card",
        installment_count="0", currency="TL", test_mode="1", non_3d="1",
        merchant_key=MERCHANT_KEY, merchant_salt=MERCHANT_SALT,
    )
    assert token == _ref(f"{MERCHANT_ID}1.2.3.4ORDER1a@b.com100.99card0TL11".encode() + MERCHANT_SALT)


# --- error tables -----------------------------------------------------------
def test_describe_known_and_unknown():
    assert "3D Secure" in describe("payment", "10")
    assert "older than one year" in describe("refund", "011")
    assert "Transaction not found" in describe("status", "004")
    assert "Transfer/EFT" in describe("payment", "4")
    assert "marketplace" in describe("transfer", "002")
    assert "marketplace" in describe("platform", "002")
    assert describe("payment", None) == ""
    assert "Unknown" in describe("refund", "777")
    # reason-style scopes are registered so they degrade gracefully.
    for scope in ("link", "bin", "installment", "card", "direct"):
        assert "Unknown" in describe(scope, "x")


def test_api_error_derives_default_message():
    # With no err_msg/reason/code, _api_error falls back to "<scope> request failed".
    err = _client()._api_error("refund", {})
    assert str(err) == "refund request failed"
    assert err.scope == "refund"
    # An explicit default still wins over the derived one.
    err2 = _client()._api_error("refund", {}, "custom default")
    assert str(err2) == "custom default"
    # A known code from the error table takes priority over the default.
    err3 = _client()._api_error("refund", {"err_no": "1"})
    assert "request failed" not in str(err3)



# --- client helpers ---------------------------------------------------------
def test_client_requires_credentials():
    with pytest.raises(Exception):
        PayTRClient(merchant_id="", merchant_key="", merchant_salt="")


def test_iframe_helpers():
    assert iframe_url("ABC123") == "https://www.paytr.com/odeme/guvenli/ABC123"
    html = iframe_html("ABC123")
    assert "https://www.paytr.com/odeme/guvenli/ABC123" in html and "iFrameResize" in html


def test_client_verify_callback():
    good = _ref(f"ORDER1{SALT_S}success3456".encode())
    assert _client().verify_callback(
        merchant_oid="ORDER1", status="success", total_amount="3456", hash=good
    )


def test_verify_link_callback_ignores_callback_id():
    good = _ref(f"ORDER1{SALT_S}success3456".encode())
    assert _client().verify_link_callback(
        merchant_oid="ORDER1", status="success", total_amount="3456",
        hash=good, callback_id="my-ref-123",
    )


async def test_direct_payment_uses_major_units_and_recurring_flags():
    """direct_payment sends major-unit "100.99" (NOT minor int) and the
    non-hashed recurring fields; recurring forces non_3d=1."""
    client = _client()
    captured: dict = {}

    async def fake_post(url, params):
        captured["url"] = url
        captured["params"] = params
        return {"status": "wait_callback"}

    client._post = fake_post  # type: ignore[method-assign]
    result = await client.direct_payment(
        merchant_oid="ORDER1", email="a@b.com", payment_amount=100.99,
        user_ip="1.2.3.4", user_name="A B", user_address="addr", user_phone="500",
        user_basket=[("X", "100.99", 1)],
        merchant_ok_url="https://x/ok", merchant_fail_url="https://x/fail",
        recurring=True, utoken="UT1", ctoken="CT1",
    )
    assert result["status"] == "wait_callback"
    assert captured["url"] == "https://www.paytr.com/odeme"
    p = captured["params"]
    assert p["payment_amount"] == "100.99"  # major units, not 10099
    assert p["non_3d"] == "1" and p["recurring_payment"] == "1"
    assert p["utoken"] == "UT1" and p["ctoken"] == "CT1"


# --- FastAPI router (no network) -------------------------------------------
def test_router_callback_and_routes():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from paytr.fastapi import create_paytr_router

    seen: list = []

    async def on_payment(data):
        seen.append(data.merchant_oid)

    app = FastAPI()
    app.include_router(create_paytr_router(_client(), on_payment=on_payment))
    tc = TestClient(app)

    # Only buyer-facing endpoints are exposed. Critical merchant operations
    # (refund, status, reports) must NOT be reachable as routes.
    paths = {r.path for r in app.routes}
    assert {
        "/paytr/pay", "/paytr/callback", "/paytr/ok", "/paytr/fail",
    } <= paths
    assert not any(
        p.startswith(("/paytr/refund", "/paytr/status", "/paytr/reports")) for p in paths
    )

    # Bad hash is rejected; valid hash runs the handler and replies OK.
    bad = tc.post("/paytr/callback", data={
        "merchant_oid": "O1", "status": "success", "total_amount": "100", "hash": "nope"
    })
    assert bad.status_code == 400 and "bad hash" in bad.text

    good_hash = _ref(f"O1{SALT_S}success100".encode())
    ok = tc.post("/paytr/callback", data={
        "merchant_oid": "O1", "status": "success", "total_amount": "100", "hash": good_hash
    })
    assert ok.status_code == 200 and ok.text == "OK"
    assert seen == ["O1"]


def test_callback_handler_failure_asks_for_retry():
    """If on_payment raises, we must NOT return OK — PayTR should retry."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from paytr.fastapi import create_paytr_router

    async def on_payment(data):
        raise RuntimeError("db down")

    app = FastAPI()
    app.include_router(create_paytr_router(_client(), on_payment=on_payment))
    tc = TestClient(app, raise_server_exceptions=False)

    good_hash = _ref(f"O2{SALT_S}success100".encode())
    resp = tc.post("/paytr/callback", data={
        "merchant_oid": "O2", "status": "success", "total_amount": "100", "hash": good_hash
    })
    assert resp.status_code == 500 and resp.text != "OK"


def _reconciling_client(expected: dict, seen: list):
    """Build a TestClient whose /callback reconciles against ``expected`` (oid -> kuruş)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from paytr.fastapi import create_paytr_router

    async def on_payment(data):
        seen.append(data.merchant_oid)

    async def get_expected_amount(merchant_oid: str):
        return expected.get(merchant_oid)

    app = FastAPI()
    app.include_router(create_paytr_router(
        _client(), on_payment=on_payment, get_expected_amount=get_expected_amount,
    ))
    return TestClient(app, raise_server_exceptions=False)


def test_callback_amount_reconciliation():
    """get_expected_amount: match -> OK, mismatch -> 400, None -> check skipped."""
    seen: list = []
    # Expected totals in minor units; "OUNK" is unknown -> resolver returns None.
    tc = _reconciling_client({"OMATCH": 100, "OBAD": 999}, seen)

    # Matching amount: handler runs, OK.
    h = _ref(f"OMATCH{SALT_S}success100".encode())
    ok = tc.post("/paytr/callback", data={
        "merchant_oid": "OMATCH", "status": "success", "total_amount": "100", "hash": h
    })
    assert ok.status_code == 200 and ok.text == "OK"

    # Mismatched amount: rejected 400, handler must NOT run.
    h = _ref(f"OBAD{SALT_S}success100".encode())
    bad = tc.post("/paytr/callback", data={
        "merchant_oid": "OBAD", "status": "success", "total_amount": "100", "hash": h
    })
    assert bad.status_code == 400 and "amount mismatch" in bad.text

    # Unknown oid -> resolver returns None -> check skipped, handler runs.
    h = _ref(f"OUNK{SALT_S}success100".encode())
    skip = tc.post("/paytr/callback", data={
        "merchant_oid": "OUNK", "status": "success", "total_amount": "100", "hash": h
    })
    assert skip.status_code == 200 and skip.text == "OK"

    assert seen == ["OMATCH", "OUNK"]  # OBAD never reached the handler


def test_callback_reconciliation_skipped_on_failure():
    """A failed payment never reconciles amounts (the success gate only checks paid orders)."""
    seen: list = []
    tc = _reconciling_client({"OFAIL": 999}, seen)
    h = _ref(f"OFAIL{SALT_S}failed100".encode())
    resp = tc.post("/paytr/callback", data={
        "merchant_oid": "OFAIL", "status": "failed", "total_amount": "100", "hash": h
    })
    # Not a success, so the mismatch check is skipped and the handler still runs.
    assert resp.status_code == 200 and resp.text == "OK"
    assert seen == ["OFAIL"]


def test_callback_non_numeric_amount_is_mismatch_not_500():
    """A non-numeric total_amount must reject as a mismatch (400), not crash to 500."""
    seen: list = []
    tc = _reconciling_client({"OWEIRD": 100}, seen)
    # The hash is computed over the literal total_amount string, so a junk value
    # can still pass the HMAC check; int() must not blow up into a retry-loop.
    h = _ref(f"OWEIRD{SALT_S}successNaN".encode())
    resp = tc.post("/paytr/callback", data={
        "merchant_oid": "OWEIRD", "status": "success", "total_amount": "NaN", "hash": h
    })
    assert resp.status_code == 400 and "amount mismatch" in resp.text
    assert seen == []
