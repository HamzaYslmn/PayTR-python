"""Configured PayTRClient singleton, shared by the app routes.

Credentials come from the environment (see src/example.env, loaded in main.py).
This is the app-glue layer (like HireUp's modules/paytr): the rest of the
package is the reusable, credential-free library.
"""

import logging
import os

from . import PayTRClient

log = logging.getLogger("paytr")

_CREDENTIALS = dict(
    merchant_id=os.environ.get("PAYTR_MERCHANT_ID", "XXXXXX"),
    merchant_key=os.environ.get("PAYTR_MERCHANT_KEY", "YYYYYYYYYYYYYY"),
    merchant_salt=os.environ.get("PAYTR_MERCHANT_SALT", "ZZZZZZZZZZZZZZ"),
    test_mode=os.environ.get("PAYTR_TEST_MODE", "1") == "1",
    debug_on=True,
)

# Default: a lazily-created aiohttp session. main.py's lifespan calls aclose().
client = PayTRClient(**_CREDENTIALS)

# To use a different backend, pass your own configured session:
#   client = PayTRClient(**_CREDENTIALS, session=httpx.AsyncClient(timeout=20))
#   client = PayTRClient(**_CREDENTIALS, session=aiohttp.ClientSession())

log.info("PayTR client ready (backend=aiohttp, test_mode=%s)", client.test_mode)
