"""Cross-module parallel group: tests from multiple modules in one package batch.

Verifies that when a package-level parallelizable("children") marker groups
tests from different modules into one parallel batch, all tests complete
and none hang due to cross-module setup/teardown interactions.
"""

INIT_SRC = (
    "import pytest\n"
    'pytestmark = pytest.mark.parallelizable("children")\n'
)

# Module A: class with function-scoped fixture (mimics ftdir pattern)
MOD_A_SRC = (
    "import threading\n"
    "\n"
    "class TestModuleA:\n"
    "    def test_a1(self, tmp_path):\n"
    "        (tmp_path / 'a1.txt').write_text(threading.current_thread().name)\n"
    "\n"
    "    def test_a2(self, tmp_path):\n"
    "        (tmp_path / 'a2.txt').write_text(threading.current_thread().name)\n"
    "\n"
    "    def test_a3(self, tmp_path):\n"
    "        (tmp_path / 'a3.txt').write_text(threading.current_thread().name)\n"
)

# Module B: different class, also uses tmp_path
MOD_B_SRC = (
    "import threading\n"
    "\n"
    "class TestModuleB:\n"
    "    def test_b1(self, tmp_path):\n"
    "        (tmp_path / 'b1.txt').write_text(threading.current_thread().name)\n"
    "\n"
    "    def test_b2(self, tmp_path):\n"
    "        (tmp_path / 'b2.txt').write_text(threading.current_thread().name)\n"
    "\n"
    "    def test_b3(self, tmp_path):\n"
    "        (tmp_path / 'b3.txt').write_text(threading.current_thread().name)\n"
)

# Module C: second class in the same module (two classes, one module)
MOD_C_SRC = (
    "import threading\n"
    "\n"
    "class TestModuleC1:\n"
    "    def test_c1(self, tmp_path):\n"
    "        (tmp_path / 'c1.txt').write_text(threading.current_thread().name)\n"
    "\n"
    "    def test_c2(self, tmp_path):\n"
    "        (tmp_path / 'c2.txt').write_text(threading.current_thread().name)\n"
    "\n"
    "class TestModuleC2:\n"
    "    def test_c3(self, tmp_path):\n"
    "        (tmp_path / 'c3.txt').write_text(threading.current_thread().name)\n"
    "\n"
    "    def test_c4(self, tmp_path):\n"
    "        (tmp_path / 'c4.txt').write_text(threading.current_thread().name)\n"
)
