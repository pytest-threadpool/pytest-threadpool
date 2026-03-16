"""Minimal service classes for the DI example."""

import threading
import uuid


class Config:
    """Application config — intended as a Singleton (shared across all tests)."""

    def __init__(self, db_url: str, pool_size: int):
        self.db_url = db_url
        self.pool_size = pool_size
        self.instance_id = uuid.uuid4()


class DbConnection:
    """Database connection — intended as ThreadLocal (one per worker thread).

    In a real app this would be sqlalchemy.Session, asyncpg.Connection, etc.
    """

    def __init__(self, config: Config):
        self.config = config
        self.instance_id = uuid.uuid4()
        self.thread_id = threading.current_thread().ident


class TestContext:
    """Per-test context — intended as ContextLocal (one per execution context).

    In a real app this would be a request context, unit-of-work, or
    transaction that should be the same instance within one test
    but fresh for each test.  Any function can resolve it from the
    container without receiving it as a parameter.
    """

    def __init__(self, config: Config):
        self.config = config
        self.instance_id = uuid.uuid4()
        self.data: dict = {}


class RequestHandler:
    """Request handler — intended as Factory (fresh instance per injection).

    In a real app this would be a use-case, service, or controller object
    that gets a fresh instance per test / per request.
    """

    def __init__(self, db: DbConnection, config: Config):
        self.db = db
        self.config = config
        self.instance_id = uuid.uuid4()
