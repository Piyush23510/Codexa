"""
Phase 4 Test Fixture: models/order.py

Class Order with save() and validate() methods —
same method names as User class to test class-scoped FQSN.
"""


class Order:
    """Represents an order entity."""

    def __init__(self, user, item):
        self.user = user
        self.item = item
        self.validate()

    def save(self):
        """Persist order to storage."""
        self.validate()
        print(f"Saving order for {self.item}")

    def validate(self):
        """Validate order data."""
        if not self.item:
            raise ValueError("Order item is required")
