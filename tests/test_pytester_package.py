"""Tests for package-level marker inheritance and overrides."""

import pytest

from tests.cases._templates import sequential_order_class


class TestPackageLevelParallel:
    """Verify package pytestmark propagation across modules and subpackages."""

    def test_package_children_cross_module(self, ftdir):
        """Package-level children batches tests from multiple modules together."""
        pkg = ftdir.mkdir("mypkg")
        pkg.joinpath("__init__.py").write_text(
            "import pytest\n"
            'pytestmark = pytest.mark.parallelizable("children")\n'
        )
        pkg.joinpath("_state.py").write_text(
            "import threading\n"
            "\n"
            "class PkgState:\n"
            "    barrier = threading.Barrier(4, timeout=10)\n"
        )
        pkg.joinpath("test_a.py").write_text(
            "from mypkg._state import PkgState\n"
            "\n"
            "class TestA:\n"
            "    def test_a1(self):\n"
            "        PkgState.barrier.wait()\n"
            "\n"
            "    def test_a2(self):\n"
            "        PkgState.barrier.wait()\n"
        )
        pkg.joinpath("test_b.py").write_text(
            "from mypkg._state import PkgState\n"
            "\n"
            "def test_b1():\n"
            "    PkgState.barrier.wait()\n"
            "\n"
            "def test_b2():\n"
            "    PkgState.barrier.wait()\n"
        )
        result = ftdir.run_pytest("--freethreaded", "4")
        result.assert_outcomes(passed=4)

    def test_subpackage_inherits_parent(self, ftdir):
        """Subpackage without own marker inherits parent's children scope."""
        pkg = ftdir.mkdir("parent")
        pkg.joinpath("__init__.py").write_text(
            "import pytest\n"
            'pytestmark = pytest.mark.parallelizable("children")\n'
        )
        sub = pkg.joinpath("sub")
        sub.mkdir()
        sub.joinpath("__init__.py").write_text("")
        sub.joinpath("_state.py").write_text(
            "import threading\n"
            "\n"
            "class SubState:\n"
            "    barrier = threading.Barrier(3, timeout=10)\n"
        )
        sub.joinpath("test_a.py").write_text(
            "from parent.sub._state import SubState\n"
            "\n"
            "def test_a1():\n"
            "    SubState.barrier.wait()\n"
            "\n"
            "def test_a2():\n"
            "    SubState.barrier.wait()\n"
        )
        sub.joinpath("test_b.py").write_text(
            "from parent.sub._state import SubState\n"
            "\n"
            "def test_b1():\n"
            "    SubState.barrier.wait()\n"
        )
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_class_override_narrows_scope(self, ftdir):
        """Class with own parameters overrides package children.
        The barrier(2) in the package batch would deadlock if
        the parametrized class joined it."""
        pkg = ftdir.mkdir("scopepkg")
        pkg.joinpath("__init__.py").write_text(
            "import pytest\n"
            'pytestmark = pytest.mark.parallelizable("children")\n'
        )
        pkg.joinpath("test_mixed.py").write_text(
            "import threading\n"
            "import pytest\n"
            "\n"
            "class TestInherits:\n"
            "    barrier = threading.Barrier(2, timeout=10)\n"
            "\n"
            "    def test_a(self):\n"
            "        self.barrier.wait()\n"
            "\n"
            "    def test_b(self):\n"
            "        self.barrier.wait()\n"
            "\n"
            '@pytest.mark.parallelizable("parameters")\n'
            "class TestNarrow:\n"
            "    param_log = {}\n"
            "\n"
            '    @pytest.mark.parametrize("x", [0, 1, 2])\n'
            "    def test_param(self, x):\n"
            "        self.param_log[x] = True\n"
            "\n"
            "    def test_verify(self):\n"
            "        assert set(self.param_log.keys()) == {0, 1, 2}\n"
        )
        result = ftdir.run_pytest("--freethreaded", "6")
        result.assert_outcomes(passed=6)

    def test_not_parallelizable_overrides_package(self, ftdir):
        """@not_parallelizable class in a parallel package runs sequentially."""
        pkg = ftdir.mkdir("notpkg")
        pkg.joinpath("__init__.py").write_text(
            "import pytest\n"
            'pytestmark = pytest.mark.parallelizable("children")\n'
        )
        pkg.joinpath("test_seq.py").write_text(
            "import pytest\n"
            "\n"
            + sequential_order_class(
                "TestSeq",
                decorator="@pytest.mark.not_parallelizable",
            )
        )
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_module_overrides_package(self, ftdir):
        """Module pytestmark overrides package marker."""
        pkg = ftdir.mkdir("modpkg")
        pkg.joinpath("__init__.py").write_text(
            "import pytest\n"
            'pytestmark = pytest.mark.parallelizable("children")\n'
        )
        pkg.joinpath("test_override.py").write_text(
            "import pytest\n"
            "\n"
            'pytestmark = pytest.mark.parallelizable("parameters")\n'
            "\n"
            + sequential_order_class("TestModOverride")
        )
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_subpackage_override(self, ftdir):
        """Subpackage with own parameters overrides parent children."""
        pkg = ftdir.mkdir("outer")
        pkg.joinpath("__init__.py").write_text(
            "import pytest\n"
            'pytestmark = pytest.mark.parallelizable("children")\n'
        )
        sub = pkg.joinpath("inner")
        sub.mkdir()
        sub.joinpath("__init__.py").write_text(
            "import pytest\n"
            'pytestmark = pytest.mark.parallelizable("parameters")\n'
        )
        sub.joinpath("test_sub.py").write_text(
            sequential_order_class("TestSubOverride")
        )
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_parallel_only_skips_without_flag(self, ftdir):
        """parallel_only marker skips tests when --freethreaded is not passed."""
        ftdir.copy_case("parallel_only_skip")
        result = ftdir.run_pytest()
        result.assert_outcomes(passed=1, skipped=1)
