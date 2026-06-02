# PayTR API Reference

A condensed but complete reference to the PayTR payment APIs, sourced from
[dev.paytr.com](https://dev.paytr.com/). This document is the integration
contract this Python package (`src/modules/paytr`) implements. When the docs and
the code disagree, treat the **live API** as the source of truth and fix the
code.

> Official docs are bilingual: Turkish at `https://dev.paytr.com/...` and English
> at `https://dev.paytr.com/en/...`. Some response field names are in Turkish
> even on the English pages (e.g. `net_tutar`, `kesinti_tutari`).

---

## 1. Core concepts

### Credentials
Every merchant has three secrets, found in the Merchant Panel under
**Information** (Bilgi). Only the **Main User** and **Technical User** can see
them.

| Credential | Meaning | Role in requests |
|---|---|---|
| `merchant_id` | Store / merchant number | Sent in plaintext on every request |
| `merchant_key` | Merchant password | HMAC **secret key** |
| `merchant_salt` | Merchant secret key | Mixed into the **signed string** |

### Signing (`paytr_token` / `hash`)
Every server-to-server request is authenticated with an HMAC-SHA256 digest,
base64-encoded. PayTR signs its own callbacks the same way. **Only the order of
the concatenated fields differs between endpoints.**

```
token = base64( HMAC_SHA256( key = merchant_key, message = <fields...> + merchant_salt ) )
```

The salt's position in the message varies per endpoint (sometimes appended,
sometimes interleaved) — see each endpoint below. In this repo the canonical
implementations live in `src/modules/paytr/_crypto.py` (one function per
concatenation order).

### Amounts
- iFrame `payment_amount` / `total_amount` and Link `price` are sent as
  **integer minor units**: multiply the major-unit price by 100. `34.56 TL` →
  `3456`.
- **Exceptions (major units, `.` decimal, e.g. `10.25`):** the Refund API's
  `return_amount` *and* the Direct/Recurring API's `payment_amount` — the latter
  differs from the iFrame, which is the classic trap.
- Basket line prices are major-unit strings (e.g. `"18.00"`).
- Repo helpers: `_money()` (major units, 2 dp), `_minor_units()` (×100 int),
  `encode_basket()` — all in `_base.py`.

### Currency
Accepted values: `TL` (alias `TRY`), `EUR`, `USD`, `GBP`, `RUB`. The repo
normalizes `TRY` → `TL` before signing/sending.

### Order id (`merchant_oid`)
Unique per order, **alphanumeric, max 64 chars**. Reused as the lookup key for
callbacks, refunds, status queries, and to deduplicate retried notifications.

### Response convention
JSON. Success → `{"status": "success", ...}`. Failure → either
`{"status": "error", "err_no": ..., "err_msg": ...}` or, for "nothing found /
not ready" cases, `{"status": "failed", ...}`. The repo treats `"failed"` as an
empty result for reports/payment-detail and as an error elsewhere.

---

## 2. Endpoint map

| Purpose | Method | URL |
|---|---|---|
| iFrame get-token (Step 1) | POST | `https://www.paytr.com/odeme/api/get-token` |
| Render iFrame | (browser) | `https://www.paytr.com/odeme/guvenli/{token}` |
| iFrame resizer JS | (browser) | `https://www.paytr.com/js/iframeResizer.min.js` |
| Refund | POST | `https://www.paytr.com/odeme/iade` |
| Status query | POST | `https://www.paytr.com/odeme/durum-sorgu` |
| Transaction detail report | POST | `https://www.paytr.com/rapor/islem-dokumu` |
| Payment statement report | POST | `https://www.paytr.com/rapor/odeme-dokumu` |
| Payment detail report | POST | `https://www.paytr.com/rapor/odeme-detayi` |
| Link create | POST | `https://www.paytr.com/odeme/api/link/create` |
| Link delete | POST | `https://www.paytr.com/odeme/api/link/delete` |
| BIN lookup | POST | `https://www.paytr.com/odeme/api/bin-detail` |
| Installment rates | POST | `https://www.paytr.com/odeme/taksit-oranlari` |
| Stored-card list | POST | `https://www.paytr.com/odeme/capi/list` |
| Stored-card delete | POST | `https://www.paytr.com/odeme/capi/delete` |
| Direct / recurring payment | POST | `https://www.paytr.com/odeme` |

All of the above are implemented in the library (§10). **Pre-authorization is
not** — its wire-level spec isn't public (see §9).

---

## 3. iFrame API

The recommended integration: PayTR hosts the payment form; you embed it in an
`<iframe>`. PCI scope stays with PayTR. Two steps: **(1)** server-side get-token,
**(2)** receive the callback.

### Step 1 — get-token
`POST https://www.paytr.com/odeme/api/get-token`

| Parameter | Req | Notes / limits |
|---|---|---|
| `merchant_id` | ✓ | |
| `user_ip` | ✓ | Customer's real IP. Max 39 (IPv6-safe) |
| `merchant_oid` | ✓ | Unique, alphanumeric, ≤64 |
| `email` | ✓ | ≤100 |
| `payment_amount` | ✓ | Integer minor units (×100) |
| `currency` | ✓ | `TL`/`TRY`/`EUR`/`USD`/`GBP`/`RUB` |
| `user_basket` | ✓ | base64(JSON) — see below |
| `no_installment` | ✓ | `1` disables installments, else `0` |
| `max_installment` | ✓ | `0`–`12`; `0` = no limit |
| `paytr_token` | ✓ | signature (below) |
| `user_name` | – | ≤60 |
| `user_address` | – | ≤400 |
| `user_phone` | – | ≤20 |
| `merchant_ok_url` | – | redirect on success, ≤400 |
| `merchant_fail_url` | – | redirect on failure, ≤400 |
| `timeout_limit` | – | minutes; default 30 |
| `test_mode` | – | `1` = test, `0` = live |
| `debug_on` | – | `1` shows error messages (dev only) |
| `lang` | – | `tr` or `en` |
| `iframe_v2` | – | `1` = new design |
| `iframe_v2_dark` | – | `1` = dark mode (with `iframe_v2=1`) |

**Basket format** — base64 of a JSON array of `[name, unitPriceString, qty]`:
```json
[["Product A","18.00",1],["Product B","33.25",2]]
```

**`paytr_token` (card):**
```
HMAC_SHA256( merchant_key,
  merchant_id + user_ip + merchant_oid + email + payment_amount +
  user_basket + no_installment + max_installment + currency + test_mode
  + merchant_salt )  → base64
```
(see `_crypto.iframe_token`)

**Success:** `{"status":"success","token":"<iframe_token>"}`
**Error:** `{"status":"error"|"failed","reason"|"err_msg":"..."}`

**Embed:**
```html
<script src="https://www.paytr.com/js/iframeResizer.min.js"></script>
<iframe src="https://www.paytr.com/odeme/guvenli/{token}"
        id="paytriframe" frameborder="0" scrolling="no"
        style="width:100%;"></iframe>
<script>iFrameResize({},'#paytriframe');</script>
```
Repo helpers: `iframe_url(token)`, `iframe_html(token)`.

### Step 2 — callback (notification)
PayTR POSTs the result to your **Callback URL** (set in the Merchant Panel) and
to `merchant_ok_url`/`merchant_fail_url` for the browser redirect. The callback
is the authoritative result — never trust the redirect alone.

POST params PayTR sends:

| Param | When | Notes |
|---|---|---|
| `merchant_oid` | always | your order id |
| `status` | always | `success` or `failed` |
| `total_amount` | always | collected amount, minor units (×100) |
| `hash` | always | verify this (below) |
| `payment_type` | always | `card` or `eft` |
| `payment_amount` | success | original Step-1 amount (×100) |
| `currency` | success | |
| `failed_reason_code` | failed | numeric, see §8 |
| `failed_reason_msg` | failed | Turkish text |
| `test_mode` | sometimes | `1` if test |

**Hash verification:**
```
HMAC_SHA256( merchant_key,
  merchant_oid + merchant_salt + status + total_amount )  → base64
```
Compare in **constant time** to the received `hash`. (see
`_crypto.verify_callback` / `PayTRClient.verify_callback`)

**You MUST:**
1. Verify the hash before doing anything.
2. Respond with the literal plain-text body `OK` (no HTML) — otherwise PayTR
   retries (~every minute).
3. Be idempotent: dedupe on `merchant_oid`; retries are normal.
4. Never gate the callback URL behind session/auth/CSRF.

---

## 4. Bank Transfer / EFT iFrame

Same get-token endpoint and embed flow as the card iFrame, but `payment_type=eft`
and a **different signature** (no basket/installment fields):

**EFT `paytr_token`:**
```
HMAC_SHA256( merchant_key,
  merchant_id + user_ip + merchant_oid + email +
  payment_amount + payment_type + test_mode  + merchant_salt )  → base64
```
(see `_crypto.eft_token`; set `payment_type="eft"` in `create_iframe_token`)
The callback arrives with `payment_type=eft`.

---

## 5. Refund API
`POST https://www.paytr.com/odeme/iade`

| Param | Req | Notes |
|---|---|---|
| `merchant_id` | ✓ | |
| `merchant_oid` | ✓ | order to refund |
| `return_amount` | ✓ | **major units**, `.` decimal (e.g. `10.25`) |
| `paytr_token` | ✓ | signature below |
| `reference_no` | – | from a status query; ≤64 alphanumeric |

Partial refunds are allowed (repeatedly, up to the remaining balance). Refunds
are not allowed for transactions older than **1 year**.

**`paytr_token`:**
```
HMAC_SHA256( merchant_key,
  merchant_id + merchant_oid + return_amount + merchant_salt )  → base64
```
(`_crypto.refund_token`)

**Success:**
```json
{"status":"success","merchant_oid":"...","return_amount":"...",
 "is_test":0,"reference_no":"..."}
```
**Error:** `{"status":"error"|"failed","err_no":"...","err_msg":"..."}` — see §8.

---

## 6. Status Query API
`POST https://www.paytr.com/odeme/durum-sorgu`

| Param | Req |
|---|---|
| `merchant_id` | ✓ |
| `merchant_oid` | ✓ |
| `paytr_token` | ✓ |

**`paytr_token`:**
```
HMAC_SHA256( merchant_key, merchant_id + merchant_oid + merchant_salt )  → base64
```
(`_crypto.status_token`)

**Success fields:** `status`, `payment_amount`, `payment_total`,
`payment_date` (`YYYY-MM-DD hh:mm:ss`), `currency`, `net_tutar`,
`kesinti_tutari`, `taksit` (0–12), `kart_marka`, `masked_pan`, `odeme_tipi`
(`CART`/`EFT`), `test_mode`, `returns` (array of refunds),
`submerchant_payments` (marketplace only).
**Not found:** `{"status":"error","err_no":"004",...}`.

---

## 7. Reporting APIs

### Transaction detail — `POST /rapor/islem-dokumu`
Params: `merchant_id`, `start_date`, `end_date` (`YYYY-MM-DD HH:MM:SS`),
`paytr_token`.
**Token:** `HMAC_SHA256(key, merchant_id + start_date + end_date + merchant_salt)`
(`_crypto.report_range_token`).
**Response rows** (Turkish keys): `islem_tipi` (`S`=sale/`I`=return),
`net_tutar`, `kesinti_tutari`, `kesinti_orani`, `islem_tutari`, `odeme_tutari`,
`islem_tarihi`, `para_birimi`, `taksit`, `kart_marka`, `kart_no` (masked),
`siparis_no`, `odeme_tipi`. `status:"failed"` = no transactions in range.

### Payment statement — `POST /rapor/odeme-dokumu`
Same param set and **same token order** as transaction detail
(`merchant_id + start_date + end_date + salt`). Date range typically
`YYYY-MM-DD`. Summary/aggregate data.

### Payment detail — `POST /rapor/odeme-detayi`
Single-day report. Params: `merchant_id`, `date` (`YYYY-MM-DD`), `paytr_token`.
**Token:** `HMAC_SHA256(key, merchant_id + date + merchant_salt)`
(`_crypto.report_date_token`).

For all reports the repo returns `[]`/`{}` when PayTR responds `status:"failed"`.

---

## 7A. Link API, queries & Direct payment (backend)

All POST, form-encoded; all signed `base64(HMAC_SHA256(merchant_key, BODY))`.
Sources corroborated against PayTR's official Postman collection.

### Link create — `POST /odeme/api/link/create`
Params: `merchant_id`, `name` (4–200), `price` (×100 int), `currency`,
`max_installment` (0–12), `link_type` (`product`|`collection`), `lang`,
`paytr_token`; conditional `min_count` (product) **or** `email` (collection);
optional `max_count`, `expiry_date` (`YYYY-MM-DD HH:MM:SS`), `callback_link`,
`callback_id` (≤64), `get_qr`, `pft`, `debug_on`.
**BODY** = `name + price + currency + max_installment + link_type + lang +
(min_count | email) + salt` (`_crypto.link_create_token`).
**Success:** `{status, id, link, qr?}`. **Error:** `{status, reason}`.

### Link delete — `POST /odeme/api/link/delete`
Params: `merchant_id`, `id`, `paytr_token`, `debug_on?`.
**BODY** = `id + merchant_id + salt` (`_crypto.link_delete_token`).
Link payment results post to `callback_link` as a **standard callback** (verify
with the §3 callback hash; `callback_id` is echoed back, **not** in the hash).

### BIN lookup — `POST /odeme/api/bin-detail`
Params: `merchant_id`, `bin_number` (6–8 digits), `paytr_token`.
**BODY** = `bin_number + merchant_id + salt` (`_crypto.bin_token`).
**Response:** `cardType`, `businessCard`, `bank`, `brand`, `schema`, `bankCode`,
`allow_non3d`.

### Installment rates — `POST /odeme/taksit-oranlari`
Params: `merchant_id`, `request_id` (≤32 unique), `paytr_token`.
**BODY** = `merchant_id + request_id + salt` (`_crypto.installment_rates_token`).
**Response:** `request_id`, `max_inst_non_bus`, `rates` (per-bank arrays).

### Stored-card list — `POST /odeme/capi/list`
Params: `merchant_id`, `utoken`, `paytr_token`.
**BODY** = `utoken + salt` — salt is **inside** the signed message, *not* a
separately appended secret (`_crypto.card_list_token`).
**Response:** `cards[]` each with `ctoken`, `last_4`, `month`, `year`, …

### Stored-card delete — `POST /odeme/capi/delete`
Params: `merchant_id`, `utoken`, `ctoken`, `paytr_token`.
**BODY** = `ctoken + utoken + salt` (salt inline, `_crypto.card_delete_token`).

### Direct / recurring payment — `POST /odeme`
Charge a card server-side (no iFrame). `payment_amount` is **major-unit string**
`"100.99"` (unlike the iFrame!). Hashed params: `merchant_id`, `user_ip`,
`merchant_oid`, `email`, `payment_amount`, `payment_type` (`card`),
`installment_count` (0–12), `currency`, `test_mode`, `non_3d`. Non-hashed extras:
`store_card`, `recurring_payment`, `utoken`, `ctoken`, `cvv` (if `require_cvv`),
plus `user_*`/`user_basket`/`merchant_ok_url`/`merchant_fail_url`.
**BODY** = `merchant_id + user_ip + merchant_oid + email + payment_amount +
payment_type + installment_count + currency + test_mode + non_3d + salt`
(`_crypto.direct_payment_token`).
**Flow:** save a card with `store_card=1` (the `utoken` comes back in the
callback); charge it later with `recurring_payment=1` + `utoken`/`ctoken`.
Recurring runs **Non3D** (store must have Non3D enabled). Immediate response
`status` ∈ `success` / `wait_callback` / `failed`; the authoritative result
arrives via the standard callback.

---

## 8. Error codes

### Payment / callback `failed_reason_code`
| Code | Meaning |
|---|---|
| 0 | Bank denial — read `failed_reason_msg` (e.g. insufficient limit/balance) |
| 1 | Customer didn't enter phone in 3D verification |
| 2 | Wrong SMS/3D password entered |
| 3 | Security check denied or unavailable |
| 6 | Customer abandoned / timed out |
| 8 | Installment not available for that card |
| 9 | Merchant not authorized for this card |
| 10 | 3D Secure required |
| 11 | Fraud / security warning |
| 99 | Technical integration error (shown when debug off) |

### Refund `err_no`
`000` service temporarily locked · `001` invalid request / inactive store ·
`002` missing `merchant_oid` · `003` missing `return_amount` · `004` token
missing/invalid · `005` no successful payment found · `007` payment not yet
notified · `008` payment type not refundable · `009` refund exceeds remaining
balance · `010` insufficient account balance · `011` transaction older than 1
year.

### Status query `err_no`
`001` invalid request / inactive store · `002` missing `merchant_oid` · `003`
token missing/invalid · `004` no transaction found.

### Platform (marketplace) transfer `err_no`
`001`–`012` request/auth/balance validation · `091`/`092` IBAN validation
(must start `TR`, 26 digits, no spaces) · `095`–`101` submerchant amount &
`transfer_name`/`transfer_iban` validation · `201`–`206` `trans_info` JSON
issues · `301`–`306` `merchant_oids` JSON issues · `BLK` order blocked (contact
support).

### Link / BIN / installment / card / direct (`reason` / `err_msg`)
These endpoints return their failure as **free text** in `reason` or `err_msg`,
not numeric code tables. `PayTRAPIError.message` surfaces that text directly;
their scopes (`link`, `bin`, `installment`, `card`, `direct`) are registered in
`errors.py` only so `describe()` degrades to a generic message.

> The repo resolves messages from these tables via `errors.describe(scope, code)`
> and surfaces them on `PayTRAPIError.message`.

---

## 9. Not implemented / out of scope

- **Pre-Authorization** (`/en/on-provizyon`) — reserve funds without capturing,
  then capture/void later. Its wire-level spec (capture/void endpoints, params,
  hash field order) is **not public** — the dev page only links to the contact
  form, and it's absent from PayTR's Postman collection. We do **not** ship
  guessed signing code for it; request the integration doc from PayTR support
  first.
- **BKM Express**, **Easy Store** (cPanel/FTP), **NeoPOS Bridge**, marketplace
  **platform transfer** — not implemented (only the platform-transfer *error
  table* is mirrored, in §8).
- **Ready-made / open-source modules** (Wix, Shopify, WooCommerce, OpenCart,
  PrestaShop, Magento, …) and the dev-portal **tools** (hash calculator, response
  observer, Postman collection) are PayTR-provided, not part of this library.

---

## 10. Going live (test → production)
1. Integrate and verify with `test_mode=1` (and `debug_on=1` while developing).
2. Use PayTR's published **test cards** (Direct API docs) for end-to-end runs.
3. Switch `test_mode` to `0` and `debug_on` to `0`.
4. Complete store activation / approval in the Merchant Panel before live
   transactions clear.

---

## 11. How this repo maps to the API

`PayTRClient` (`client.py`) is assembled from one mixin per API, each in its own
module so no file grows unwieldy:

| Module | Mixin | Methods |
|---|---|---|
| `iframe_api.py` | `IframeMixin` | `create_iframe_token` (card / `payment_type="eft"`), `iframe_url`/`iframe_html` |
| `link_api.py` | `LinkMixin` | `create_payment_link`, `delete_payment_link`, `verify_link_callback` |
| `refund_api.py` | `RefundMixin` | `refund` |
| `status_api.py` | `StatusMixin` | `status` |
| `reporting_api.py` | `ReportingMixin` | `transaction_detail`, `payment_statement`, `payment_detail` |
| `direct_api.py` | `DirectMixin` | `direct_payment`, `list_cards`, `delete_card`, `bin_detail`, `installment_rates` |
| `_base.py` | `_BaseClient` | construction, HTTP lifecycle, `_post`, `_api_error`, `verify_callback`, amount/basket helpers |

- `_crypto.py` — one signing function per concatenation order (see §3–§7A).
- `errors.py` — `describe(scope, code)` maps `err_no`/`failed_reason_code` to the
  §8 tables; `scope` ∈ {`payment`, `refund`, `status`, `transfer`/`platform`,
  and the reason-style `link`/`bin`/`installment`/`card`/`direct`}.
- `exceptions.py` — `PayTRError` → `PayTRConfigError`, `PayTRNetworkError`,
  `PayTRAPIError` (carries `code`, `scope`, `payload`).
- `fastapi.py` — **optional** (`[fastapi]` extra; pulls in pydantic).
  `include_paytr_routes(app, client, on_payment=...)` wires only the buyer-facing
  get-token + callback (+ ok/fail) routes; every other operation is backend-only.

> **Gotchas to keep in mind:** minor-units everywhere *except* refund
> `return_amount` **and** direct/recurring `payment_amount` (major-unit string);
> always verify the callback hash and reply `OK`; callbacks retry and must be
> idempotent; `TRY`→`TL`; EFT and direct-payment tokens each sign a different
> field set than the card iFrame; `capi/list` & `capi/delete` fold the salt
> *into* the signed message.
