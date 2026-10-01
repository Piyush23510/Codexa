"""
Phase 4 Test Fixture: utils_b.py

Contains parse() and helper() — same names as utils_a.py
to test duplicate function name resolution.
"""


def parse(data):
    """Parse data using strategy B."""
    cleaned = helper(data)
    return cleaned.lower()


def helper(raw):
    """Internal helper for utils_b."""
    return raw.replace("\n", " ")
