# pytest-threaded

Parallel test execution for free-threaded Python builds (3.13t+).

Runs test *bodies* concurrently in a `ThreadPoolExecutor` while keeping
fixture setup/teardown sequential (pytest internals are not thread-safe).

## Installation

```bash
pip install pytest-threaded
```

## Quick start

```bash
PYTHON_GIL=0 pytest --threaded auto
```

Mark tests for parallel execution:

```python
from pytest_threaded import parallelizable, not_parallelizable

import pytest

@parallelizable("children")     # methods run in parallel
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

| Scope        | Effect                                                  |
|--------------|---------------------------------------------------------|
| `children`   | Direct children of the marked node run concurrently     |
| `parameters` | Parametrized variants of the same test run concurrently |
| `all`        | Combines `children` + `parameters`                      |

## Marker levels

Markers can be applied at function, class, module (`pytestmark`), or
package (`__init__.py` `pytestmark`) level. Priority (most specific wins):

```
not_parallelizable > own marker > class > module > package
```

## Usage

```bash
# Auto-detect thread count
PYTHON_GIL=0 pytest --threaded auto

# Fixed thread count
PYTHON_GIL=0 pytest --threaded 8

# Normal sequential run (no flag)
pytest
```

## License

MIT
