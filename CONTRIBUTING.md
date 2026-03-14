# Contributing to pytest-freethreaded

## Development setup

```bash
# Clone and install in editable mode
git clone <repo-url>
cd pytest-freethreaded
pip install -e .

# Run tests (3.14t has GIL off by default, no PYTHON_GIL=0 needed)
pytest --freethreaded auto
```

> **Note:** `PYTHON_GIL=0` is only required on Python 3.13t.
> Python 3.14t ships with the GIL disabled by default.

## Architecture rules

### No module-level executable code

All modules define classes, functions, constants, and imports only. No mutable
state, no object construction, no side effects at import time.

`__init__.py` files contain only markers and imports — never barriers, dicts,
lists, or other state.

The single exception is `plugin.py`, which defines bare functions that pytest
discovers as hooks.

### One module, one class

Each module contains a single primary class. A second class is only allowed
when it is tightly coupled to the first (e.g., two enums in the same domain).
If a class grows unrelated responsibilities, split it into a new module.

### Shared state lives in classes

Any mutable state needed across tests or across a test run must be held as
class attributes or instance attributes — never as module-level variables.

```python
# Good
class TestState:
    log = {}
    barrier = threading.Barrier(3, timeout=10)

# Bad
_log = {}
_barrier = threading.Barrier(3, timeout=10)
```

### Access on need, not on import

State should be created and accessed at the point of use. Importing a module
should not trigger construction of barriers, connections, or other resources.

### Parallelism tests use pytester

Tests that verify parallel execution (barriers, concurrent writes, thread counts)
must use the `pytester` fixture and `runpytest_subprocess`. This ensures each test
spawns an isolated subprocess with the correct `--freethreaded` flag, so tests
are self-contained and pass regardless of how the outer runner is invoked.

```python
# Good — isolated subprocess
def test_children_run_concurrently(self, pytester):
    pytester.makepyfile("""
        import threading, pytest
        @pytest.mark.parallelizable("children")
        class TestBarrier:
            barrier = threading.Barrier(2, timeout=10)
            def test_a(self): self.barrier.wait()
            def test_b(self): self.barrier.wait()
    """)
    result = pytester.runpytest_subprocess("--freethreaded", "auto")
    result.assert_outcomes(passed=2)

# Bad — depends on outer runner flags
class TestBarrier:
    barrier = threading.Barrier(2, timeout=10)
    def test_a(self): self.barrier.wait()
    def test_b(self): self.barrier.wait()
```

### Constants over strings

Use `ParallelScope` enum and `_constants` module instead of bare string
literals. Any string that appears in more than one location belongs in
`_constants.py`. Enums must use `StrEnum` (not `str, Enum`).

### Plugin hooks are wiring only

`plugin.py` hook functions delegate to classes immediately. No business logic
in hook functions — keep them thin.

## Project structure

```
src/pytest_freethreaded/
    __init__.py       # Public API: parallelizable, not_parallelizable
    _constants.py     # ParallelScope and _GroupPrefix enums
    _markers.py       # MarkerResolver: marker introspection
    _grouping.py      # GroupKeyBuilder: parallel batch grouping
    _fixtures.py      # FixtureManager: finalizer save/restore
    _runner.py        # ParallelRunner: parallel execution orchestration
    plugin.py         # pytest hook implementations (wiring only)
```

## Running tests

```bash
# Run all tests (pytester tests spawn their own subprocesses)
pytest -v
```
