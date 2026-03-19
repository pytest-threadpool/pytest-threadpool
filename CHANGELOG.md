# Changelog

## 0.4.0

### Highlights

- **Interactive live-view terminal UI** (`--threadpool-output live`) with
  split-pane layout, test tree navigation, and real-time output inspection.

### Live-view features

- **Split-pane layout**: `Tab` opens a tree panel on the left with the main
  content on the right, both independently scrollable.
- **Test tree**: Full session hierarchy (packages > modules > classes > tests)
  with live outcome markers (`✓` passed, `✗` failed, `E` error, `s` skipped,
  `x` xfail, `X` xpass). Groups show aggregated status.
- **Fuzzy search**: Type in the tree panel to fuzzy-filter tests (fzf-style
  subsequence matching). `Escape` clears the query.
- **Context switching**: `Enter` on a test shows its captured output (stdout,
  stderr, logs, colored tracebacks) in the content pane. `Enter` on a group
  shows combined output for all descendants. `Summary` node returns to the
  main progress view.
- **Outcome filters**: `Ctrl+P` toggles passed test visibility, `Ctrl+X`
  toggles failed test visibility. Empty groups are automatically hidden.
- **Content search**: `/` activates vim-style search within the content pane.
  `n`/`N` navigate matches. Current match highlighted in orange, other matches
  in grey. `Escape` clears search.
- **Save to file**: `Ctrl+W` saves the full active buffer (ANSI-stripped) to
  `logs/{name}_{timestamp}.log`.
- **Focus switching**: `Ctrl+←`/`Ctrl+→` switches keyboard focus between panes.
  Mouse scroll targets whichever pane the cursor is over.
- **Keybinds hint line**: Bottom bar shows available keyboard shortcuts.
- **Configurable tree width**: `threadpool_tree_width` ini setting (supports
  `pyproject.toml`, `pytest.ini`).

### Test outcome markers

- Added `x` (xfail), `X` (xpass), and `E` (setup/teardown error) markers
  to the live reporter alongside existing `.` (pass), `F` (fail), `s` (skip).
- Sequential nodeid-style output now shows `XFAIL`, `XPASS`, and `ERROR` words.

### Scroll responsiveness

- Fixed scroll input being unresponsive after tests finish — root cause was
  multiple competing `InputReader` threads stealing from the shared terminal
  input buffer on free-threaded Python.
- `InputReader` now uses `os.dup()` to create a private fd immune to pytest
  capture redirections.
- Device-level singleton ensures only one active reader per terminal device.
- `ensure_entered()` uses `threading.Event` + lock for thread-safe
  initialization on free-threaded Python.
- `ensure_cbreak()` uses `TCSANOW` to avoid flushing pending input.

### Architecture

- Region-based dirty tracking (`Region` enum) for independent pane rendering
  without cross-pane flicker.
- `Display.redraw_buffer()` supports `left_offset` for split-pane rendering,
  `highlight`/`highlight_line` for search result visualization.
- `Display.redraw_pane()` and `redraw_separator()` for side panel rendering.

### Tests

- Integration tests for all test outcome markers (pass, fail, skip, xfail,
  xpass, error) in both classic and live modes.
- Integration test for tree panel rendering.
- Unit tests for tree overlay (navigation, fuzzy search, outcome filters,
  group markers, expand/collapse).
- Unit tests for content search highlighting.
- Unit tests for scroll latency.

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
