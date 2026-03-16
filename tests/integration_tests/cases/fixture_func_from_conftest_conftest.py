"""Conftest providing a function-scoped fixture for the conftest fixture test."""

import pytest


@pytest.fixture
def conftest_resource(request):
    """Function-scoped fixture defined in conftest (no explicit scope)."""
    return f"conftest_{request.node.name}"
