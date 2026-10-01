"""
Phase 4 Test Fixture: models/user.py

Class User with save() and validate() methods —
same method names as Order class to test class-scoped FQSN.
"""


class User:
    """Represents a user entity."""

    def __init__(self, name):
        self.name = name
        self.validate()

    def save(self):
        """Persist user to storage."""
        self.validate()
        print(f"Saving user {self.name}")

    def validate(self):
        """Validate user data."""
        if not self.name:
            raise ValueError("User name is required")
