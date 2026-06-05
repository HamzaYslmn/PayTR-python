"""Configured PayTRClient singleton, shared by the demo app routes.

Credentials come from the environment (see src/example.env, loaded in main.py).
This is the demo's app-glue layer — it lives here, outside the ``paytr``
package, so the library itself stays reusable and credential-free.
"""

import logging
import os

from paytr import PayTRClient

log = logging.getLogger("paytr")

_CREDENTIALS = dict(
    merchant_id=os.environ.get("PAYTR_MERCHANT_ID", "XXXXXX"),
    merchant_key=os.environ.get("PAYTR_MERCHANT_KEY", "YYYYYYYYYYYYYY"),
    merchant_salt=os.environ.get("PAYTR_MERCHANT_SALT", "ZZZZZZZZZZZZZZ"),
    test_mode=os.environ.get("PAYTR_TEST_MODE", "1") == "1",
    debug_on=os.environ.get("PAYTR_DEBUG_ON", "0") == "1",
)

# Default: a lazily-created aiohttp session. main.py's lifespan calls aclose().
client = PayTRClient(**_CREDENTIALS)

# To use a different backend, pass your own configured session:
#   client = PayTRClient(**_CREDENTIALS, session=httpx.AsyncClient(timeout=20))
#   client = PayTRClient(**_CREDENTIALS, session=aiohttp.ClientSession())

log.info("PayTR client ready (test_mode=%s)", client.test_mode)
