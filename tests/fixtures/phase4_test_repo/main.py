"""
Phase 4 Test Fixture: main.py

Entry point that imports from multiple modules,
exercising cross-file dependencies and aliases.
"""

from utils_a import parse as parse_a
from utils_b import parse as parse_b
from models.user import User
from models.order import Order


def run_pipeline(data):
    """Main pipeline that calls functions from multiple modules."""
    cleaned_a = parse_a(data)
    cleaned_b = parse_b(data)

    user = User("alice")
    user.save()

    order = Order(user, "item_1")
    order.save()

    return cleaned_a, cleaned_b


def report(results):
    """Generate a report from pipeline results."""
    for r in results:
        print(r)
