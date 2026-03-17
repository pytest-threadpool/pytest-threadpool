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
