# Roadmap

## Capture fixture support (capsys / capfd / caplog)

**Goal:** Make `capsys`, `capfd`, and `caplog` work transparently in parallel tests.

**Problem:** These fixtures assume exclusive ownership of global state (`sys.stdout`,
root logger) during a test's lifetime. When multiple tests run concurrently, output
interleaves and pytest raises "cannot use capsys and capsys at the same time".
`caplog` leaks records across tests, and `at_level()` context managers race on the
shared root logger.

**Approach:** Delayed replay — collect output per-worker during parallel execution,
then feed it back one item at a time during the sequential reporting phase.

- **capsys/capfd:** The `_ThreadLocalStream` proxy already buffers worker output
  into per-thread `StringIO`. Instead of discarding on `deactivate()`, associate
  each buffer with its test item and flush to the real stream before
  `pytest_runtest_makereport` reads the capture.

- **caplog:** Install a per-thread `logging.Handler` that collects records into a
  thread-local list. During sequential reporting, replay records into caplog's
  handler so the fixture sees the correct records for each test.

**Edge cases to handle:**
- Nested captures (fixtures that call `capsys.readouterr()` mid-test)
- `caplog.at_level()` context managers across threads
- Fixtures that mix capsys with print output
- `capfd` (file descriptor level) vs `capsys` (sys.stdout level)

**Priority:** High — this is the most common friction point for adoption.

## Harden FixtureDef cloning

**Goal:** Make function-scoped fixture cloning more robust against pytest internals
changes and more transparent to developers.

**Current approach:** `clone_function_fixturedefs` uses `__new__` + `__dict__.update`
for a shallow copy, then resets `cached_result` and `_finalizers`. This works because
those are the only two fields mutated during fixture lifecycle — but it's fragile.

**Improvements:**

- **Deep-copy guard:** Validate at clone time that the only mutable fields are the
  ones we reset. If a future pytest version adds mutable state to `FixtureDef`,
  the clone should fail loudly (assertion or warning) rather than silently sharing
  state across workers.

- **Document fixture chain isolation:** When fixture A (function-scoped) depends on
  fixture B (also function-scoped), both get cloned independently. Chain resolution
  works because `_arg2fixturedefs` is replaced as a whole, so `getfixturevalue("B")`
  hits B's clone. This is correct but non-obvious — add inline comments explaining
  the chain resolution path through the cloned map.

- **`object.__setattr__` on `_arg2fixturedefs`:** Currently bypasses the `Final`
  typing annotation. If pytest ever enforces immutability at runtime (frozen
  dataclass, `__slots__`), this breaks. Track whether upstream adds a setter or
  public mutation API.

**Priority:** Medium — current implementation works, but one pytest release could
break it silently.

## Plugin compatibility testing

Validate and document interactions with commonly used pytest plugins:

- `pytest-randomly` — test reordering vs parallel group formation
- `pytest-timeout` — per-test timeouts in worker threads
- `pytest-repeat` — repeated test execution in parallel groups
- `pytest-cov` — coverage collection across worker threads

## Public pytest API migration

Track pytest releases for public equivalents of internal APIs currently used:

- `_pytest.fixtures.FixtureDef._finalizers`
- `_pytest.fixtures.FixtureDef.cached_result`
- `_pytest.setupplan.SetupState.stack`
- `_pytest.scope.Scope`
- `callspec._arg2scope`

Migrate to public APIs as they become available to reduce breakage risk
across pytest releases.
