# paytr-python

A small, typed, **async** Python library for the [PayTR](https://dev.paytr.com/en)
payment APIs — with **optional ready-to-use FastAPI routes**. The client is built
on `aiohttp` (or bring your own `httpx`); FastAPI + `pydantic` are only pulled in
by the optional `[fastapi]` extra, so `import paytr` stays dependency-light.

Covers most of the PayTR surface. Only the **buyer-facing purchase flow** is
exposed as routes. Everything else — refund, status, reporting, payment links,
stored cards, BIN / installment queries and direct/recurring payment — is
**backend-only**: a `PayTRClient` method with no route, called from your own
trusted server-side code (never the browser). Build your own user-scoped,
authenticated endpoint on top if buyers need self-service.

| Capability | PayTR endpoint | Client method | Route |
| --- | --- | --- | --- |
| iFrame token (STEP 1, **new design v2**, card + Havale/EFT) | `/odeme/api/get-token` | `create_iframe_token()` | `POST /paytr/pay` |
| Callback verification (STEP 2) | your URL | `verify_callback()` | `POST /paytr/callback` |
| Refund (full / partial) | `/odeme/iade` | `refund()` | _backend only_ |
| Status query | `/odeme/durum-sorgu` | `status()` | _backend only_ |
| Transaction-detail report | `/rapor/islem-dokumu` | `transaction_detail()` | _backend only_ |
| Payment statement / summary | `/rapor/odeme-dokumu` | `payment_statement()` | _backend only_ |
| Payment-detail report | `/rapor/odeme-detayi` | `payment_detail()` | _backend only_ |
| Create / delete payment link | `/odeme/api/link/{create,delete}` | `create_payment_link()` / `delete_payment_link()` | _backend only_ |
| BIN lookup | `/odeme/api/bin-detail` | `bin_detail()` | _backend only_ |
| Installment rates | `/odeme/taksit-oranlari` | `installment_rates()` | _backend only_ |
| Stored cards (list / delete) | `/odeme/capi/{list,delete}` | `list_cards()` / `delete_card()` | _backend only_ |
| Direct / recurring payment | `/odeme` | `direct_payment()` | _backend only_ |

Plus the official **error-code tables** (`paytr.describe(scope, code)`).

> **Not implemented:** pre-authorization — its wire-level spec isn't public
> (contact PayTR for the integration doc). It is deliberately left out rather
> than guessed, since this is payment-signing code.

## Install

```bash
pip install "paytr-python[fastapi]"   # client + FastAPI routes
pip install paytr-python              # client only (no FastAPI dependency)
```

Credentials (`merchant_id`, `merchant_key`, `merchant_salt`) are on the **BİLGİ /
INFORMATION** page of the PayTR Merchant Panel. Keep the key and salt secret.

**Test cards** (only valid with `test_mode=True`; name and expiry are free-form,
CVV `000`): `4355084355084358`, `5406675406675403`, `9792030394440796` — exp e.g.
`12/30`, holder "PAYTR TEST". The iFrame test form injects these for you; you'll
need them for `direct_payment` testing.

## 1. Ready-to-use FastAPI routes

```python
from fastapi import FastAPI
from paytr import PayTRClient
from paytr.fastapi import include_paytr_routes, CallbackData

app = FastAPI()
client = PayTRClient(
    merchant_id="123456", merchant_key="...", merchant_salt="...",
    test_mode=True,   # use PayTR test cards; flip to False in production
)

async def on_payment(data: CallbackData) -> None:
    # Verified callback. Idempotent: act once per merchant_oid (PayTR retries).
    if data.is_success:
        ...  # credit the order
    else:
        print("payment failed:", data.error_message)

include_paytr_routes(app, client, on_payment=on_payment)   # mounts everything
```

That mounts, under `/paytr` (configurable via `prefix=`):

```
POST /paytr/pay              create a V2 iFrame token (STEP 1)
POST /paytr/callback         payment result callback (STEP 2, PayTR -> you)
GET  /paytr/ok, /paytr/fail  default buyer redirect targets
```

That's the whole buyer purchase flow — nothing more. Every merchant-only
operation (**refund**, **status**, **reporting**, **links**, **stored cards**,
**BIN / installment**, **direct payment**) is deliberately *not* routed; call
`client.refund()` / `client.status()` / `client.create_payment_link()` etc. from
your own trusted backend (see §2).

Nothing is mounted at `/` — everything stays under the prefix so it won't clash
with your app's routes. Optional knobs: `prefix`, `ok_url`, `fail_url`. Use
`create_paytr_router(...)` instead if you want the `APIRouter` to include
yourself.

### `POST /paytr/pay` body

```json
{
  "email": "buyer@example.com",
  "user_name": "Jane Buyer",
  "user_address": "Somewhere 1",
  "user_phone": "05551112233",
  "basket": [{"name": "Item 1", "unit_price": 18.0, "quantity": 1}],
  "currency": "TL",
  "lang": "tr"
}
```

Amounts are in **major units** (e.g. `18.0` ₺). The library handles the ×100
conversion, basket encoding, and HMAC signing. Response:
`{"status": "success", "merchant_oid": "...", "token": "...", "iframe_url": "..."}`.
Render the iframe with that `iframe_url` (and the PayTR resizer script).

## 2. The client (framework-agnostic)

```python
from paytr import PayTRClient, iframe_html

client = PayTRClient(merchant_id="...", merchant_key="...", merchant_salt="...")

result = await client.create_iframe_token(
    merchant_oid="ORDER123",
    email="buyer@example.com",
    payment_amount="34.56",
    user_ip="1.2.3.4",
    user_name="Jane Buyer",
    user_address="Somewhere 1",
    user_phone="05551112233",
    user_basket=[("Item 1", "18.00", 1), ("Item 2", "16.56", 1)],
    merchant_ok_url="https://shop.example.com/ok",
    merchant_fail_url="https://shop.example.com/fail",
)
html = iframe_html(result["token"])

# Other backend calls
await client.refund(merchant_oid="ORDER123", return_amount="11.90")
await client.status("ORDER123")
await client.transaction_detail(start_date="2021-02-02 00:00:00", end_date="2021-02-04 23:59:59")
await client.payment_statement(start_date="2022-09-01", end_date="2022-09-30")
await client.payment_detail("2022-09-15")

# Payment links (price in major units)
link = await client.create_payment_link(name="T-Shirt", price=14.45, min_count=1)
await client.delete_payment_link(link["id"])

# Queries
await client.bin_detail("435508")            # card brand / bank / 3D eligibility
await client.installment_rates("req-123")    # your commission rates

# Stored cards + recurring (store must have Non3D enabled)
cards = await client.list_cards(utoken)       # utoken comes back in the callback
await client.direct_payment(
    merchant_oid="ORDER124", email="buyer@example.com",
    payment_amount="34.56",                   # NOTE: major-unit string, unlike the iFrame
    user_ip="1.2.3.4", user_name="Jane", user_address="Somewhere 1", user_phone="0555...",
    user_basket=[("Item 1", "34.56", 1)],
    merchant_ok_url="https://shop.example.com/ok",
    merchant_fail_url="https://shop.example.com/fail",
    recurring=True, utoken=utoken, ctoken=cards["cards"][0]["ctoken"],
)
```

> **Amount gotcha:** `create_iframe_token` / link `price` take **minor-unit
> integers** (the library ×100s major units for you), but `refund` and
> `direct_payment` take a **major-unit string** like `"34.56"`. Pick the right
> method — they're signed differently.

Verifying a callback manually:

```python
ok = client.verify_callback(
    merchant_oid=oid, status=status, total_amount=total_amount, hash=received_hash
)  # always verify before trusting the data; then reply with plain text "OK"
```

## Errors

Non-success API responses raise `PayTRAPIError` (`.message`, `.code`, `.scope`,
`.payload`); transport/decoding issues raise `PayTRNetworkError`; bad config
raises `PayTRConfigError`. All inherit from `PayTRError`. Resolve a raw code:

```python
from paytr import describe
describe("payment", "10")  # -> "3D Secure required for this transaction"
describe("refund", "009")  # -> "Refund exceeds the remaining transaction amount"
```

## Logging

The library logs through the dedicated `paytr` logger, configured automatically
on import — no setup call needed. It attaches one handler to the `paytr` logger
only (never the root logger) with propagation off, so it won't interfere with or
double-print through your app's logging.

```python
import os
os.environ["PAYTR_LOG"] = "off"      # don't auto-configure; you own the logger
os.environ["PAYTR_LOG"] = "debug"    # or set the level (debug/info/warning/...)

# or at runtime:
from paytr import setup_logging
setup_logging("DEBUG", use_colors=False)   # idempotent; force=True to replace
```

To route PayTR logs through your own handlers, set `PAYTR_LOG=off` and configure
`logging.getLogger("paytr")` however you like.

## HTTP session & lifecycle

Bring your own session for full control of timeouts, connection limits, proxies
or retries — you'll never hit limits we picked for you:

```python
PayTRClient(..., session=my_aiohttp_session)     # backend auto-detected
PayTRClient(..., session=my_httpx_async_client)  # backend auto-detected
```

With no session, a default **aiohttp** session is created lazily:

```python
PayTRClient(...)               # aiohttp (default), 30s timeout
PayTRClient(..., timeout=None) # no timeout imposed by us
PayTRClient(..., timeout=10)   # 10s timeout on the default session
```

To use httpx, just pass an `httpx.AsyncClient` as `session=` (install the
`[httpx]` extra).

Reuse one instance (it pools connections) and close it on shutdown
(`await client.aclose()`), or use it as an async context manager. A session you
pass in via `session=` is yours to manage — we never close it.

## Demo app

The `src/` tree is a runnable example app (`src` layout; the library lives under
`src/modules/paytr` and imports as `paytr`):

```
src/
  main.py            # loads .env, CORS, auto-discovers api/ routers
  modules/paytr/     # the library (+ _client.py: configured singleton)
  api/payment.py     # mounts the library router (create_paytr_router)
  api/page.py        # serves the test page at /paytr/
  web/index.html     # standalone test page (served, or opened as a file)
```

```bash
uv sync --all-extras
cp src/example.env .env             # fill in real credentials
cd src && uv run main.py            # http://127.0.0.1:8000/paytr/
uv run pytest                       # tests (no network)
uv run python test/excardtest.py    # create a test token + iFrame URL
```
