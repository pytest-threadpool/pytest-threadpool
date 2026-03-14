# pytest-freethreaded

Parallel test execution for free-threaded Python builds (3.13t+).

Runs test *bodies* concurrently in a `ThreadPoolExecutor` while keeping
fixture setup/teardown sequential (pytest internals are not thread-safe).

> **Note:** Python 3.14t ships with the GIL disabled by default —
> `PYTHON_GIL=0` is only needed on 3.13t. We recommend using 3.14t+
> for the best free-threaded experience.

## Installation

```bash
pip install pytest-freethreaded
```

## Quick start

```bash
# Python 3.14t (GIL off by default)
pytest --freethreaded auto

# Python 3.13t (must disable GIL explicitly)
PYTHON_GIL=0 pytest --freethreaded auto
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
