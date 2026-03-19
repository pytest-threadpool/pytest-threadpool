# pytest-threadpool

[![PyPI - Version](https://img.shields.io/pypi/v/pytest-threadpool)](https://pypi.org/project/pytest-threadpool/)
[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.13t%20%7C%203.14%20%7C%203.14t%20%7C%203.15%20%7C%203.15t-blue?logo=python&logoColor=white)](https://pypi.org/project/pytest-threadpool/)
[![License](https://img.shields.io/github/license/pytest-threadpool/pytest-threadpool)](https://github.com/pytest-threadpool/pytest-threadpool/blob/main/LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-pytest--threadpool-blue?logo=github)](https://github.com/pytest-threadpool/pytest-threadpool)
[![CI](https://github.com/pytest-threadpool/pytest-threadpool/actions/workflows/ci.yml/badge.svg)](https://github.com/pytest-threadpool/pytest-threadpool/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/pytest-threadpool/pytest-threadpool/branch/main/graph/badge.svg)](https://codecov.io/gh/pytest-threadpool/pytest-threadpool)

**Status: Beta** · Parallel test execution using threads.

Runs test *bodies*, function-scoped fixture setup, and function-scoped fixture
teardown concurrently in a thread pool while keeping shared fixtures
(module/class/session scope) sequential.

Works on any Python 3.13+. Free-threaded builds (3.13t, 3.14t, 3.15t) get true
parallelism for CPU-bound tests. Standard builds still benefit from parallel
execution of I/O-bound tests (network, database, file operations).

## Installation

```bash
pip install pytest-threadpool
```

## Quick start

```bash
pytest --threadpool auto
```

Mark tests for parallel execution:

```python
from pytest_threadpool import parallelizable, not_parallelizable

import pytest


@parallelizable("children")  # all nested tests run in parallel
class TestMyFeature:
  def test_a(self): ...

  def test_b(self): ...


@parallelizable("parameters")  # parametrized variants run in parallel
@pytest.mark.parametrize("x", [1, 2, 3])
def test_with_params(x): ...


@parallelizable("all")  # children + parameters combined
class TestEverything:
  @pytest.mark.parametrize("n", [1, 2])
  def test_param(self, n): ...

  def test_plain(self): ...


@not_parallelizable  # opt out of inherited parallelism
def test_must_be_sequential(): ...
```

## Scopes

| Scope        | Effect                                                            |
|--------------|-------------------------------------------------------------------|
| `children`   | All nested tests run concurrently (children, grandchildren, etc.) |
| `parameters` | Parametrized variants of the same test run concurrently           |
| `all`        | Combines `children` + `parameters`                                |

## Fixture handling

Function-scoped fixtures are cloned per-item and set up in parallel alongside
test calls. Each worker gets independent fixture instances — no shared mutable
state between concurrent fixture setups.

Shared fixtures (module, class, and session scope) are resolved once
sequentially before workers launch and served from cache to all items.

| Scope      | Behavior                                                |
|------------|---------------------------------------------------------|
| `function` | Cloned per-item, setup and teardown in parallel workers |
| `class`    | Resolved once, cached, shared across items              |
| `module`   | Resolved once, cached, shared across items              |
| `session`  | Resolved once, cached, shared across items              |

Shared fixture teardown runs sequentially after the parallel group completes.

## Marker levels

Markers can be applied at function, class, module (`pytestmark`), or
package (`__init__.py` `pytestmark`) level. Priority (most specific wins):

```
not_parallelizable > own marker > class > module > package
```

## Shared state between tests

Unlike `pytest-xdist`, which uses subprocesses and requires all test data to
be pickleable, `pytest-threadpool` runs tests in threads within a **single
process**. This means tests can share common non-pickleable, thread-safe
objects — both within a parallel group and across sequential groups:

```python
import threading

from pytest_threadpool import parallelizable


class SharedState:
  lock = threading.Lock()  # not pickleable
  event = threading.Event()  # not pickleable
  results = {}


@parallelizable("children")
class TestGroupA:
  def test_a1(self):
    with SharedState.lock:
      SharedState.results["a1"] = True

  def test_a2(self):
    with SharedState.lock:
      SharedState.results["a2"] = True


@parallelizable("children")
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
pytest --threadpool auto

# Fixed thread count
pytest --threadpool 8

# Normal sequential run (no flag)
pytest
```

To enable `--threadpool` by default, add it to your config:

**pyproject.toml** (pytest 9.0+):

```toml
[tool.pytest]
addopts = ["--threadpool", "auto"]
```

**pytest.ini**:

```ini
[pytest]
addopts = --threadpool auto
```

## Configuration

### Command-line options

| Option                | Values            | Default   | Description                                                                                                   |
|-----------------------|-------------------|-----------|---------------------------------------------------------------------------------------------------------------|
| `--threadpool`        | `N` or `auto`     | *(off)*   | Enable parallel execution with N threads. `auto` uses `os.cpu_count()`.                                       |
| `--threadpool-output` | `classic`, `live` | `classic` | Output mode. `live` opens an interactive terminal viewer with scroll, tree navigation, and real-time updates. |

### INI settings

Set in `pyproject.toml`, `pytest.ini`, or `setup.cfg`:

| Setting                 | Type | Default | Description                                                                     |
|-------------------------|------|---------|---------------------------------------------------------------------------------|
| `threadpool_tree_width` | int  | `0`     | Width (columns) of the live-view tree pane. `0` = auto (1/4 of terminal width). |

**pyproject.toml:**

```toml
[tool.pytest]
threadpool_tree_width = "35"

# or under ini_options
[tool.pytest.ini_options]
threadpool_tree_width = "35"
```

**pytest.ini:**

```ini
[pytest]
threadpool_tree_width = "35"
```

### Live-view keybindings

Available when `--threadpool-output live` is active:

| Key               | Action                                               |
|-------------------|------------------------------------------------------|
| `↑` `↓`           | Scroll content / move tree cursor                    |
| `PgUp` `PgDn`     | Page scroll                                          |
| `Home` `End`      | Jump to top / bottom                                 |
| `Tab`             | Toggle tree panel (split-pane)                       |
| `Enter`           | Show test/group output in content pane               |
| `←` `→`           | Collapse/expand tree node                            |
| `Ctrl+←` `Ctrl+→` | Switch keyboard focus between tree and content panes |
| `Ctrl+P`          | Toggle show/hide passed tests in tree                |
| `Ctrl+X`          | Toggle show/hide failed tests in tree                |
| `/`               | Search within content pane (when focused)            |
| `n` / `N`         | Jump to next / previous search match                 |
| `Ctrl+W`          | Save current pane content to `.log` file             |
| Mouse scroll      | Scrolls whichever pane the cursor is over            |
| `Escape`          | Clear search / close tree                            |
| `Ctrl+C`          | Exit                                                 |

The tree panel shows the full test hierarchy (session > packages > modules > classes > tests)
with live outcome markers (`✓` passed, `✗` failed, `E` error, `s` skipped, `x` xfail, `X` xpass).
Groups show aggregated status. Type in the tree panel to fuzzy-filter tests (fzf-style).

## Tested versions

| Component | Versions                              |
|-----------|---------------------------------------|
| Python    | 3.13, 3.13t, 3.14, 3.14t, 3.15, 3.15t |
| pytest    | 9.0.2                                 |

> **Note:** On standard (GIL-enabled) builds, the GIL limits parallel speedup
> for CPU-bound tests. I/O-bound tests still run concurrently.

## Examples

The [`examples/`](examples/) directory contains runnable usage patterns:

- **DI container** — dependency injection with Singleton, ThreadLocal, ContextLocal, and Factory scopes
- **Event bus** — shared in-memory test double with concurrent producers and aggregate verification
- **Parallel logging** — shared thread-safe log collector (caplog alternative)
- **Shared state** — barriers, atomic counters, and cross-group coordination
- **User pool** — custom thread pool with LIFO queue recycling

The [`tests/integration_tests/cases/`](tests/integration_tests/cases/) and
[`tests/integration_tests/`](tests/integration_tests/) directories are also
worth browsing for real-world grouping, fixture, and reporting scenarios.

## Known limitations

- **Private pytest API usage** — The plugin relies on internal `_pytest` APIs
  (fixture finalizers, setup state, terminal writer) that have no public
  equivalents. These may break across pytest releases without warning.
- **No plugin compatibility guarantees** — Interactions with other pytest
  plugins (e.g. `pytest-xdist`, `pytest-timeout`, `pytest-randomly`) are
  untested and may conflict.
- **No `capsys`/`capfd` in parallel** — These fixtures are not thread-safe.
  `capsys`/`capfd` fail with "cannot use capsys and capsys at the same time"
  when requested by parallel tests. Alternatives:
  - **`print()`** — Worker output is buffered by thread-local stream
    proxies and reported alongside each test's result. In default capture
    mode, output appears in "Captured stdout call" sections on failure.
    With `-vs` (`--capture=no -v`), captured output is emitted after the
    PASSED/FAILED line for each test. TTY mode (default without `-s`)
    suppresses print output; use `-vs` to see it. A TTY-friendly output
    viewer with switchable per-thread/per-test frames is planned (see
    [ROADMAP](ROADMAP.md)).
  - **`caplog`** — The `caplog` fixture works natively in parallel tests.
    `caplog.records`, `caplog.text`, `caplog.record_tuples`,
    `caplog.messages`, `caplog.clear()`, `caplog.at_level()`, and
    `caplog.set_level()` all behave the same as in sequential pytest.
    Each worker gets its own `LogCaptureHandler` with per-thread record
    isolation — parallel tests don't leak records into each other's
    caplog. Failed tests show "Captured log call" sections as expected.
  - **`logging.Logger`** — Standard `logging` calls (`logger.info()`,
    `logger.warning()`, etc.) work natively in parallel tests. A
    thread-local log handler captures records per-worker and attaches
    them to "Captured log call" report sections on failure, matching
    sequential pytest behavior. Log output does not appear in stdout
    for passing tests unless `--log-cli-level` is set or a
    `StreamHandler` explicitly targets `sys.stdout` or `sys.stderr`.
    `--log-level` controls which records are captured. Existing
    `StreamHandler` instances are automatically redirected through
    the per-thread proxy so their output is grouped per-test instead
    of interleaving globally.
  - **IDE and CI runners (PyCharm, TeamCity, VS Code)** — Each test's
    function-scoped setup, call, and teardown output appears in its own
    report. Shared fixture output (session/package/module/class setup
    and teardown) is emitted at the suite level, not inside individual
    tests. Parametrized tests are reported in collection order so
    runners group them correctly. Works via the `teamcity-messages`
    plugin (`--teamcity` flag); PyCharm and TeamCity CI use the same
    protocol.
  - **Custom output hook** — Implement `pytest_threadpool_report` in a
    conftest or plugin to customize how captured worker output is handled.
    Return `True` to suppress the default output handling.

## License

[Apache 2.0](LICENSE)
