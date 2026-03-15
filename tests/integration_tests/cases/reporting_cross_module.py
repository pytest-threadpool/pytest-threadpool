"""Case data for cross-module incremental reporting test.

Not a test file itself — the outer test creates a package structure
from these source strings.
"""

INIT_SRC = 'import pytest\npytestmark = pytest.mark.parallelizable("children")\n'

MOD_A_SRC = (
    "import time\n\ndef test_fast_a():\n    pass\n\ndef test_slow_a():\n    time.sleep(0.3)\n"
)

MOD_B_SRC = (
    "import time\n\ndef test_fast_b():\n    pass\n\ndef test_slow_b():\n    time.sleep(0.3)\n"
)
