"""Tests for test result reporting under parallel execution."""

import json
import re
import shutil

import pytest

from pathlib import Path

from tests.cases.reporting_cross_module import INIT_SRC, MOD_A_SRC, MOD_B_SRC
from tests.cases import reporting_package_children as pkg_children

CASES_DIR = Path(__file__).parent / "cases"


class TestReporting:
    """Verify that test results are reported correctly with --freethreaded."""

    def test_incremental_within_class(self, ftdir):
        """Within a single class, fast tests are reported before the slow one.

        Uses a conftest plugin that records monotonic timestamps when
        pytest_runtest_logreport fires. All tests share the same file,
        so fast tests report as dots on the same line before the slow
        test finishes.
        """
        shutil.copy2(
            CASES_DIR / "reporting_incremental.py",
            ftdir.path / "test_case.py",
        )
        shutil.copy2(
            CASES_DIR / "reporting_incremental_conftest.py",
            ftdir.path / "conftest.py",
        )
        result = ftdir.run_pytest("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        log_path = ftdir.path / "report_log.json"
        assert log_path.exists(), (
            f"report_log.json not created\nstdout:\n{result.stdout}"
        )
        entries = json.loads(log_path.read_text())
        assert len(entries) == 4

        fast_times = []
        slow_time = None
        for e in entries:
            if "test_slow" in e["nodeid"]:
                slow_time = e["timestamp"]
            else:
                fast_times.append(e["timestamp"])

        assert slow_time is not None, "slow test not found in report log"
        assert len(fast_times) == 3, "expected 3 fast tests in report log"

        for ft in fast_times:
            assert ft < slow_time, (
                f"Fast test reported at {ft} >= slow test at {slow_time}. "
                "Reporting is not incremental."
            )

    def test_cross_module_fast_not_blocked(self, ftdir):
        """Fast tests from one module report while another module's slow
        test is still running — no blocking across files.

        Module A: test_fast (instant) + test_slow (0.3s)
        Module B: test_fast (instant) + test_slow (0.3s)

        Both fast tests should be reported before either slow test,
        proving that module A's slow test does not block module B.
        """
        pkg = ftdir.mkdir("reporting_pkg")
        pkg.joinpath("__init__.py").write_text(INIT_SRC)
        pkg.joinpath("test_a.py").write_text(MOD_A_SRC)
        pkg.joinpath("test_b.py").write_text(MOD_B_SRC)
        shutil.copy2(
            CASES_DIR / "reporting_incremental_conftest.py",
            ftdir.path / "conftest.py",
        )
        result = ftdir.run_pytest("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        log_path = ftdir.path / "report_log.json"
        assert log_path.exists(), (
            f"report_log.json not created\nstdout:\n{result.stdout}"
        )
        entries = json.loads(log_path.read_text())
        assert len(entries) == 4

        fast_times = []
        slow_times = []
        for e in entries:
            if "slow" in e["nodeid"]:
                slow_times.append(e["timestamp"])
            else:
                fast_times.append(e["timestamp"])

        assert len(fast_times) == 2, f"expected 2 fast tests, got {fast_times}"
        assert len(slow_times) == 2, f"expected 2 slow tests, got {slow_times}"

        max_fast = max(fast_times)
        min_slow = min(slow_times)
        assert max_fast < min_slow, (
            f"Fast tests not all reported before slow tests. "
            f"Latest fast: {max_fast}, earliest slow: {min_slow}. "
            "A slow test in one module is blocking reporting from another."
        )

    def test_package_children_all_concurrent(self, ftdir):
        """Tests from classes and bare functions across modules all run
        in the same parallel batch under package children scope."""
        pkg = ftdir.mkdir("childpkg")
        pkg.joinpath("__init__.py").write_text(pkg_children.INIT_SRC)
        pkg.joinpath("test_a.py").write_text(pkg_children.MOD_A_SRC)
        pkg.joinpath("test_b.py").write_text(pkg_children.MOD_B_SRC)
        pkg.joinpath("test_c.py").write_text(pkg_children.MOD_C_SRC)
        shutil.copy2(
            CASES_DIR / "reporting_incremental_conftest.py",
            ftdir.path / "conftest.py",
        )
        result = ftdir.run_pytest("--freethreaded", "6")
        result.assert_outcomes(passed=6)

        log_path = ftdir.path / "report_log.json"
        entries = json.loads(log_path.read_text())
        assert len(entries) == 6

        fast_times = []
        slow_times = []
        for e in entries:
            if "slow" in e["nodeid"]:
                slow_times.append((e["nodeid"], e["timestamp"]))
            else:
                fast_times.append((e["nodeid"], e["timestamp"]))

        assert len(fast_times) == 3
        assert len(slow_times) == 3

        # Fast tests come from all three modules
        fast_nodeids = {n for n, _ in fast_times}
        assert any("test_a" in n for n in fast_nodeids), "no fast test from module A"
        assert any("test_b" in n for n in fast_nodeids), "no fast test from module B"
        assert any("test_c" in n for n in fast_nodeids), "no fast test from module C"

        # All fast tests reported before any slow test
        max_fast = max(t for _, t in fast_times)
        min_slow = min(t for _, t in slow_times)
        assert max_fast < min_slow, (
            f"Fast tests not all reported before slow tests. "
            f"Latest fast: {max_fast}, earliest slow: {min_slow}."
        )

    def test_same_file_dots_grouped(self, ftdir):
        """Within a single file, dots appear on one line (no split)."""
        shutil.copy2(
            CASES_DIR / "reporting_incremental.py",
            ftdir.path / "test_case.py",
        )
        result = ftdir.run_pytest("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        dot_lines = [
            l for l in result.outlines
            if re.search(r"test_case\.py\s+\.", l)
        ]
        assert len(dot_lines) == 1, (
            f"Expected test_case.py on exactly 1 line, got {len(dot_lines)}: "
            f"{dot_lines}\nstdout:\n{result.stdout}"
        )
