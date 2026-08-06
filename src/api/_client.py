"""Configured PayTRClient singleton, shared by the demo app routes.

Credentials come from the PAYTR_* environment variables (see src/example.env,
loaded in main.py). main.py's lifespan calls ``client.aclose()`` on shutdown.
"""

import logging

from paytr import PayTRClient

log = logging.getLogger("paytr")

client = PayTRClient.from_env()
# For custom timeouts/proxies pass your own session:
#   client = PayTRClient.from_env(session=aiohttp.ClientSession())

log.info("PayTR client ready (test_mode=%s)", client.test_mode)
