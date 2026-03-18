# Roadmap

## Capture fixture support (capsys / capfd / caplog)

**Goal:** Make `capsys`, `capfd`, and `caplog` work transparently in parallel tests.

**Problem:** These fixtures assume exclusive ownership of global state (`sys.stdout`,
root logger) during a test's lifetime. When multiple tests run concurrently, output
interleaves and pytest raises "cannot use capsys and capsys at the same time".
`caplog` leaks records across tests, and `at_level()` context managers race on the
shared root logger.

**Current state:**

- **stdout/stderr capture:** Worker stdout/stderr is captured per-item by
  `_ThreadLocalStream` and associated with the test item via `captured_output`.
  The `deactivate()` method returns buffered content, which is attached to
  `report.sections` and (in passive/`-s` mode) emitted to real stdout after
  the result line. A `pytest_threadpool_report` hook allows plugins to
  customize output handling.

- **Logging (done):** Standard `logging.Logger` calls work natively in
  parallel tests. A `_ThreadLocalLogHandler` on the root logger captures
  records per-worker into thread-local lists. On completion, records are
  attached to "Captured log call" report sections on failure, matching
  sequential pytest behavior. `--log-level` controls which records are
  captured. Existing `StreamHandler` instances (targeting `sys.stdout` or
  `sys.stderr`) are automatically patched during parallel execution so
  their output flows through the per-thread proxy and is grouped per-test
  instead of leaking to global output.

**Remaining work:**

- **capsys/capfd:** Bridge the per-item captured output into pytest's capture
  infrastructure so `capsys.readouterr()` returns the correct content.
  Currently the stream proxy operates independently of pytest's capture
  mechanism — the two need to be wired together.

- **caplog fixture (done):** The `caplog` fixture works natively in parallel
  tests. A fresh `LogCaptureHandler` is installed per-worker and bridged
  to the thread-local log handler via record forwarding. `caplog.records`,
  `caplog.text`, `caplog.record_tuples`, `caplog.messages`, `caplog.clear()`,
  `caplog.at_level()`, and `caplog.set_level()` all work as expected.
  Cross-test record isolation is guaranteed — each worker's caplog sees
  only its own records. The root logger's `setLevel` is patched to use
  thread-local storage during parallel execution, preventing `at_level()`
  races across threads.

**Edge cases to handle:**
- Nested captures (fixtures that call `capsys.readouterr()` mid-test)
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

## TTY output viewer

**Goal:** A CLI-level TTY wrapper that gives real-time visibility into
parallel test execution — overall progress, global-scope output, and
switchable per-thread or per-test output frames.

**Problem:** In TTY mode, worker `print()` output is buffered and only
surfaces on failure or when the user passes `-vs` to disable capture.
Users cannot see output from running tests in real time, and there is
no way to inspect individual worker activity during execution.

**Current state:** The per-worker buffer infrastructure is in place
(`_ThreadLocalStream` captures per-item, `captured_output` stores it,
`pytest_threadpool_report` hook allows plugins to consume it).
Shared-scope fixture output (session/package/module/class) is properly
scoped and emitted at the suite level. The live reporter already tracks
per-file/per-item state with ANSI cursor movement.

**Design:**

- **Top area — overall progress:** Compact status showing total
  progress, pass/fail counts, and elapsed time. Always visible
  regardless of which frame is selected.

- **Global frame (default):** Shows global-scope output in real time —
  session/package/module/class fixture setup and teardown, collection
  messages, and warnings. This is the default view when no specific
  thread or test is focused.

- **Per-thread frames:** Switch focus to a specific worker thread to
  stream its buffered output live. Unfocused workers continue buffering
  silently, indicated by status dots or spinners in the progress area.

- **Per-test frames:** Switch focus to a specific test to see its
  setup, call, and teardown output. Completed tests show their full
  captured output; running tests stream live.

- **Frame switching:** Keyboard shortcuts or arrow keys to cycle between
  global, per-thread, and per-test views. Similar to
  `docker compose logs --follow` with service selection.

**Control:** `--threadpool-output=live|buffered` flag for explicit
selection. Default: `live` when stdout is a TTY, `buffered` otherwise.

**Priority:** Medium — currently users need `-vs` to see output, which
is a clear workaround but a friction point for adoption.

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
