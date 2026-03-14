"""Fixtures with interdependent finalizers: A depends on B, B must teardown after A."""
import pytest


teardown_order = []


@pytest.fixture
def db_connection():
    teardown_order.append("db_setup")
    yield "conn"
    teardown_order.append("db_teardown")


@pytest.fixture
def db_transaction(db_connection):
    teardown_order.append("tx_setup")
    yield f"tx({db_connection})"
    teardown_order.append("tx_teardown")


@pytest.mark.parallelizable("children")
class TestInterdependentFinalizers:
    def test_a(self, db_transaction):
        assert db_transaction == "tx(conn)"

    def test_b(self, db_transaction):
        assert db_transaction == "tx(conn)"


def test_verify_teardown_order():
    """tx_teardown must appear before db_teardown (LIFO)."""
    tx_indices = [i for i, v in enumerate(teardown_order) if v == "tx_teardown"]
    db_indices = [i for i, v in enumerate(teardown_order) if v == "db_teardown"]
    for tx_i, db_i in zip(tx_indices, db_indices):
        assert tx_i < db_i, (
            f"tx_teardown at {tx_i} must come before db_teardown at {db_i}: "
            f"{teardown_order}"
        )
