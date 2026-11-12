"""Tiny calculator with one deliberate bug for localization demos."""


def add(a, b):
    return a + b


def divide(a, b):
    # BUG: no zero-division guard
    return a / b


class Calculator:
    """Stateful calculator."""

    def __init__(self):
        self.total = 0

    def run(self, a, b):
        self.total = add(a, b)
        return divide(self.total, b)
