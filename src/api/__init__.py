"""HTTP routes for the paytr-python demo app.

Each module here exposes a ``router`` that ``main.py`` auto-discovers and mounts.
Underscore-prefixed modules are skipped by discovery; the configured PayTR
singleton lives in ``api._client``.
"""
