# pytest-freethreaded

Parallel test execution for free-threaded Python builds (3.13t+).

Runs test *bodies* concurrently in a `ThreadPoolExecutor` while keeping
fixture setup/teardown sequential (pytest internals are not thread-safe).

## Installation

```bash
pip install pytest-freethreaded
```

## Quick start

```bash
pytest --freethreaded auto
```

Mark tests for parallel execution:

```python
from pytest_freethreaded import parallelizable, not_parallelizable

import pytest

@parallelizable("children")     # all nested tests run in parallel
class TestMyFeature:
    def test_a(self): ...
    def test_b(self): ...

@parallelizable("parameters")   # parametrized variants run in parallel
@pytest.mark.parametrize("x", [1, 2, 3])
def test_with_params(x): ...

@parallelizable("all")          # children + parameters combined
class TestEverything:
    @pytest.mark.parametrize("n", [1, 2])
    def test_param(self, n): ...
    def test_plain(self): ...

@not_parallelizable             # opt out of inherited parallelism
def test_must_be_sequential(): ...
```

## Scopes

| Scope        | Effect                                                            |
|--------------|-------------------------------------------------------------------|
| `children`   | All nested tests run concurrently (children, grandchildren, etc.) |
| `parameters` | Parametrized variants of the same test run concurrently           |
| `all`        | Combines `children` + `parameters`                                |

## Marker levels

Markers can be applied at function, class, module (`pytestmark`), or
package (`__init__.py` `pytestmark`) level. Priority (most specific wins):

```
not_parallelizable > own marker > class > module > package
```

## Shared state between tests

Unlike `pytest-xdist`, which uses subprocesses and requires all test data to
be pickleable, `pytest-freethreaded` runs tests in threads within a **single
process**. This means tests can share common non-pickleable, thread-safe
objects — both within a parallel group and across sequential groups:

```python
import threading
import pytest


class SharedState:
    lock = threading.Lock()          # not pickleable
    event = threading.Event()        # not pickleable
    results = {}


@pytest.mark.parallelizable("children")
class TestGroupA:
    def test_a1(self):
        with SharedState.lock:
            SharedState.results["a1"] = True

    def test_a2(self):
        with SharedState.lock:
            SharedState.results["a2"] = True


@pytest.mark.parallelizable("children")
class TestGroupB:
    def test_b1(self):
        SharedState.event.set()
        with SharedState.lock:
            SharedState.results["b1"] = True

    def test_b2(self):
        assert SharedState.event.wait(timeout=10)
        with SharedState.lock:
            SharedState.results["b2"] = True
```

Objects like `threading.Lock`, `threading.Event`, `logging.Logger`, database
connections, and other non-pickleable resources can live as class attributes
and be accessed freely from any test — parallel or sequential — without
serialization overhead or workarounds.

## Usage

```bash
# Auto-detect thread count
pytest --freethreaded auto

# Fixed thread count
pytest --freethreaded 8

# Normal sequential run (no flag)
pytest
```

## License

MIT
