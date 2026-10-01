"""
Phase 4 Test Fixture: utils_a.py

Contains parse() and helper() — same names as utils_b.py
to test duplicate function name resolution.
"""


def parse(data):
    """Parse data using strategy A."""
    cleaned = helper(data)
    return cleaned


def helper(raw):
    """Internal helper for utils_a."""
    return raw.strip()
