"""
Phase 4 Test Fixture: services/processor.py

Uses imports with aliases, cross-module calls,
and class instantiation to test complex resolution scenarios.
"""

from models.user import User
from models.order import Order
from utils_a import parse as clean_parse


def process_all(raw_data):
    """Process data through the full pipeline."""
    cleaned = clean_parse(raw_data)

    user = User("test_user")
    user.save()

    order = Order(user, cleaned)
    order.save()

    return order


def _internal_helper():
    """Private helper function."""
    pass


class Processor:
    """Orchestrates processing tasks."""

    def __init__(self):
        self.results = []

    def run(self, data):
        """Run the processor on input data."""
        result = process_all(data)
        self.results.append(result)
        return result

    def reset(self):
        """Clear stored results."""
        self.results = []
