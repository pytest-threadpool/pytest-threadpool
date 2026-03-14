"""conftest that fakes a GIL-enabled Python build for testing the validation."""
import sysconfig

_original = sysconfig.get_config_vars


def _patched(*args):
    result = _original(*args)
    if isinstance(result, dict):
        result = dict(result)
        result["Py_GIL_DISABLED"] = 0
    return result


sysconfig.get_config_vars = _patched
