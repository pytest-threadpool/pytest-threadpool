"""Case data for package-level children reporting test.

Package with children scope containing classes and bare functions
across multiple modules. All should be treated as children of the
package and run in one parallel batch.
"""

INIT_SRC = (
    "import pytest\n"
    'pytestmark = pytest.mark.parallelizable("children")\n'
)

# Module A: one class with a fast method and a slow method
MOD_A_SRC = (
    "import time\n"
    "\n"
    "class TestClassA:\n"
    "    def test_fast(self):\n"
    "        pass\n"
    "\n"
    "    def test_slow(self):\n"
    "        time.sleep(0.3)\n"
)

# Module B: another class with a fast method and a slow method
MOD_B_SRC = (
    "import time\n"
    "\n"
    "class TestClassB:\n"
    "    def test_fast(self):\n"
    "        pass\n"
    "\n"
    "    def test_slow(self):\n"
    "        time.sleep(0.3)\n"
)

# Module C: bare functions, one fast and one slow
MOD_C_SRC = (
    "import time\n"
    "\n"
    "def test_fast_func():\n"
    "    pass\n"
    "\n"
    "def test_slow_func():\n"
    "    time.sleep(0.3)\n"
)
