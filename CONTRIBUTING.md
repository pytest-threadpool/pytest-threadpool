# Contributing to pytest-freethreaded

## Development setup

```bash
git clone <repo-url>
cd pytest-freethreaded
./scripts/setup-dev        # defaults to python 3.14t
./scripts/setup-dev 3.13t  # or specify a version
```

This installs a free-threaded Python via uv, syncs all dependencies (including
dev tools), and sets up a pre-commit hook that runs `ruff format`, `ruff check`,
and `pyright` before each commit.

> Python 3.13t and 3.14t ship with the GIL disabled by default.

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

### Parallelism tests use `ftdir` fixture

Tests that verify parallel execution (barriers, concurrent writes, thread counts)
must use the `ftdir` fixture (defined in `conftest.py`) and `run_pytest`. Unlike
`pytester`, `ftdir` is thread-safe — it uses `tmp_path` instead of `os.chdir()`,
so tests can run in parallel via `--freethreaded` on the outer suite itself.

Each test writes files into its own `tmp_path` directory and runs pytest as a
subprocess with the exact thread count needed. Use explicit thread counts for
barrier-based tests (not `auto`) to avoid deadlocks on low-core machines.

```python
# Good — isolated subprocess via ftdir, explicit thread count
def test_children_run_concurrently(self, ftdir):
    ftdir.makepyfile("""
        import threading, pytest
        @pytest.mark.parallelizable("children")
        class TestBarrier:
            barrier = threading.Barrier(2, timeout=10)
            def test_a(self): self.barrier.wait()
            def test_b(self): self.barrier.wait()
    """)
    result = ftdir.run_pytest("--freethreaded", "2")
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
    __init__.py       # Re-exports only
    _api.py           # Public API: parallelizable, not_parallelizable
    _constants.py     # ParallelScope and _GroupPrefix enums
    _markers.py       # MarkerResolver: marker introspection
    _grouping.py      # GroupKeyBuilder: parallel batch grouping
    _fixtures.py      # FixtureManager: finalizer save/restore
    _runner.py        # ParallelRunner: parallel execution orchestration
    plugin.py         # pytest hook implementations (wiring only)

hooks/
    pre-commit        # Git pre-commit hook (ruff + pyright)

scripts/
    setup-dev         # One-command dev environment setup
```

## Commit message style

Every commit message starts with one or more tags in brackets:

```
[Tag] Short description
```

### Tags

| Tag | Scope |
|-----|-------|
| `[Runner]` | Core parallel execution engine (`_runner.py`, `_fixtures.py`) |
| `[Markers]` | Marker resolution and grouping (`_markers.py`, `_grouping.py`, `_constants.py`) |
| `[Report]` | Terminal reporting and display (`_LiveReporter`) |
| `[Plugin]` | Plugin hooks and CLI options (`plugin.py`) |
| `[API]` | Public API changes (`_api.py`, `__init__.py`) |
| `[Test]` | Test additions or changes only |
| `[Tooling]` | Ruff, pyright, pre-commit, CI, scripts |
| `[Docs]` | README, CONTRIBUTING, docstrings |
| `[Refactor]` | Internal restructuring, no behavior change |
| `[Fix]` | Bug fix — must include issue number if fixing a known issue |

### Combining tags

Tags can be combined. The fix tag always comes first and includes the issue
number when one exists:

```
[Fix #42][Runner] Prevent deadlock when setup fails mid-group
[Fix][Report] Correct progress count after skipped tests
[Test][Markers] Add coverage for nested package marker inheritance
[Tooling] Add ruff PIE and RET rule sets
```

## Running tests

```bash
# Run all tests in parallel (each test spawns its own subprocess)
pytest --freethreaded auto

# Run sequentially
pytest -v
```
