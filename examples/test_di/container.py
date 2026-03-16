"""DI container wiring four provider scopes — pure stdlib, no GIL re-enablement.

- Singleton:      one Config for the entire session
- ThreadLocal:    one DbConnection per worker thread
- ContextLocal:   one TestContext per test (survives await, reset between tests)
- Factory:        fresh RequestHandler every injection

All providers are class attributes — use ``Container.config()`` etc. directly.

.. note::

   The `dependency-injector <https://github.com/ets-labs/python-dependency-injector>`_
   library offers similar provider scopes, but its C-extension is not marked as
   free-threaded safe.  On 3.13t+ builds Python will fall back to the GIL-enabled
   interpreter when it is imported, negating the benefit of free-threaded execution.
   This example uses pure-stdlib providers to avoid that limitation.
"""

from examples.test_di.providers import ContextLocal, Factory, Singleton, ThreadLocal
from examples.test_di.services import Config, DbConnection, RequestHandler, TestContext


class Container:
    config = Singleton(
        Config,
        db_url="postgresql://localhost/testdb",
        pool_size=4,
    )

    db_connection = ThreadLocal(
        DbConnection,
        config=config,
    )

    test_context = ContextLocal(
        TestContext,
        config=config,
    )

    request_handler = Factory(
        RequestHandler,
        db=db_connection,
        config=config,
    )
