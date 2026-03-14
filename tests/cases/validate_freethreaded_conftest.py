"""conftest that fakes a GIL-enabled Python build for testing the validation."""
import sysconfig

_original = sysconfig.get_config_var


def _patched(name):
    if name == "Py_GIL_DISABLED":
        return 0
    return _original(name)


sysconfig.get_config_var = _patched
