# Changelog

## 0.3.6

### Fixes

- Fixed session, module, and class-scoped fixtures being torn down and
  re-created between parallel groups instead of being resolved once and
  shared for their entire scope. The same fix applies to xunit-style
  `setup_module`/`setup_class` hooks.

## 0.3.5

### Fixes

- Fixed crash (KeyError) when a worker thread throws an unexpected exception
  outside the normal test lifecycle — failures are now reported gracefully
  instead of taking down the entire test run.
- `--threadpool` with a non-numeric value (e.g. `--threadpool foo`) now raises
  a clean `pytest.UsageError` instead of an unhandled `ValueError` traceback.
- `@parallelizable("children")` applied directly to a test function now emits
  a warning explaining that functions have no children, instead of being
  silently ignored.

### Cleanup

- Moved `ParallelScope` import to module top in `_markers.py`, removed
  misleading circular-import comment.

## 0.3.4

### Highlights

- GIL-enabled builds now supported — `--threadpool` no longer raises
  `UsageError` on non-free-threaded Python; it issues a warning instead
  and runs with GIL-limited parallelism.
- Thread-safe stdout/stderr capture via `_ThreadLocalStream` proxy,
  preventing worker `print()` output from corrupting test result lines.
- Package-group merging — split package-level parallel groups (interrupted
  by sequential `@not_parallelizable` items) are merged back together.

### New examples

- DI container, parallel logging, user pool with LIFO queue, shared state
  patterns (barrier, atomic counter, async counter).

### Improvements

- Cross-module package groups correctly initialize per-module shared fixtures.
- Mixed parallel/sequential reporting with `nodeid PASSED` format.
- Live reporter line separation fixes between groups and transitions.

### Build & CI

- Python version matrix expanded to 3.13, 3.13t, 3.14, 3.14t, 3.15, 3.15t.
- Codecov integration, CI ignores tag pushes.

## 0.3.3

### Build & CI

- Added GitHub Actions workflows for CI and PyPI publishing.
- Integrated `hatch-vcs` for automatic version management.

## 0.3.2

### Features

- Parallelized function-scoped fixture teardowns — `yield` cleanup,
  `addfinalizer` callbacks, and xunit `teardown_method` now run in
  worker threads alongside test calls.

## 0.3.1

### Cleanup

- Removed unused `selenium` dependency.

## 0.3.0

### Features

- Parallelized function-scoped fixture setups — each worker creates
  independent fixture instances from cloned `FixtureDef` objects.
- Shared fixtures (module/class/session) resolved once sequentially
  before workers launch.

## 0.2.0

- Initial beta release with core parallel execution engine.
- Marker-based parallelism (`children`, `parameters`, `all`).
- Priority chain: `not_parallelizable` > own > class > module > package.
