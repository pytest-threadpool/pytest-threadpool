# Contributing to pytest-threaded

## Development setup

```bash
# Clone and install in editable mode
git clone <repo-url>
cd pytest-threaded
pip install -e .

# Run tests
PYTHON_GIL=0 pytest --threaded auto
```

## Architecture rules

### No module-level executable code

All modules define classes, functions, constants, and imports only. No mutable
state, no object construction, no side effects at import time.

`__init__.py` files contain only markers and imports — never barriers, dicts,
lists, or other state.

The single exception is `plugin.py`, which defines bare functions that pytest
discovers as hooks.

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

### Constants over strings

Use `ParallelScope` enum and `_constants` module instead of bare string
literals. Any string that appears in more than one location belongs in
`_constants.py`.

### Plugin hooks are wiring only

`plugin.py` hook functions delegate to classes immediately. No business logic
in hook functions — keep them thin.

## Project structure

```
src/pytest_threaded/
    __init__.py       # Public API: parallelizable, not_parallelizable
    _constants.py     # Enums and string constants
    _markers.py       # MarkerResolver: marker introspection
    _grouping.py      # GroupKeyBuilder: parallel batch grouping
    _fixtures.py      # FixtureManager: finalizer save/restore
    _runner.py        # ParallelRunner: parallel execution orchestration
    plugin.py         # pytest hook implementations (wiring only)
```

## Running tests

```bash
# Full suite with parallel execution
pytest --threaded auto -v

# Without parallel (parallel_only tests will skip)
pytest -v
```
