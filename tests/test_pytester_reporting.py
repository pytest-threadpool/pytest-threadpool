"""Tests for test result reporting under parallel execution."""

import json
import re
import shutil
from pathlib import Path

from tests.cases import reporting_package_children as pkg_children
from tests.cases.reporting_cross_module import INIT_SRC, MOD_A_SRC, MOD_B_SRC

CASES_DIR = Path(__file__).parent / "cases"

MULTI_FILE_INIT = 'import pytest\npytestmark = pytest.mark.parallelizable("children")\n'
MULTI_FILE_A = "def test_a1():\n    pass\n\ndef test_a2():\n    pass\n"
MULTI_FILE_B = "def test_b1():\n    pass\n\ndef test_b2():\n    pass\n"


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
        assert log_path.exists(), f"report_log.json not created\nstdout:\n{result.stdout}"
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
        assert log_path.exists(), f"report_log.json not created\nstdout:\n{result.stdout}"
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

        dot_lines = [line for line in result.outlines if re.search(r"test_case\.py\s+\.", line)]
        assert len(dot_lines) == 1, (
            f"Expected test_case.py on exactly 1 line, got {len(dot_lines)}: "
            f"{dot_lines}\nstdout:\n{result.stdout}"
        )


def _setup_multi_file_pkg(ftdir):
    """Create a two-module package for output mode tests."""
    pkg = ftdir.mkdir("mpkg")
    pkg.joinpath("__init__.py").write_text(MULTI_FILE_INIT)
    pkg.joinpath("test_a.py").write_text(MULTI_FILE_A)
    pkg.joinpath("test_b.py").write_text(MULTI_FILE_B)


def _render_terminal(raw):
    """Replay raw PTY output into final visible screen lines.

    Handles \\n (newline), \\r (carriage return), ESC[nA (cursor up),
    ESC[nB (cursor down), ESC[K (erase to EOL), and strips other
    ANSI CSI/OSC sequences.
    """
    # Split into tokens: ANSI sequences, \r, \n, or plain text
    tokens = re.findall(r"\033\[[^a-zA-Z]*[a-zA-Z]|\033\][^\x07]*\x07|\r|\n|[^\033\r\n]+", raw)

    lines = [""]
    row = 0

    for tok in tokens:
        if tok == "\n":
            row += 1
            while row >= len(lines):
                lines.append("")
        elif tok == "\r":
            pass  # carriage return — next write overwrites from col 0
        elif tok.startswith("\033[") and tok.endswith("A"):
            # cursor up
            n = int(tok[2:-1]) if tok[2:-1] else 1
            row = max(0, row - n)
        elif tok.startswith("\033[") and tok.endswith("B"):
            # cursor down
            n = int(tok[2:-1]) if tok[2:-1] else 1
            row += n
            while row >= len(lines):
                lines.append("")
        elif tok.startswith("\033[") and tok.endswith("K"):
            # erase to end of line
            lines[row] = ""
        elif tok.startswith("\033"):
            pass  # ignore other escapes
        else:
            # plain text — overwrite current line from start
            # (we always \r\033[K before writing, so line is cleared)
            lines[row] = lines[row] + tok

    return [line for line in lines if line.strip()]


def _strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\033\][^\x07]*\x07", "", re.sub(r"\033\[[^a-zA-Z]*[a-zA-Z]", "", text))


# Regex matching a result line: "path/to/test.py .." with result letters
_RESULT_LINE_RE = re.compile(r"test_[ab]\.py\s+[.Fs]+")


class TestDumbMode:
    """Verify output in dumb/pipe mode (non-TTY subprocess)."""

    def test_one_line_per_file(self, ftdir):
        """Each file appears exactly once — no duplicates."""
        _setup_multi_file_pkg(ftdir)
        result = ftdir.run_pytest("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        a_lines = [line for line in result.outlines if re.search(r"test_a\.py\s+[.Fs]+", line)]
        b_lines = [line for line in result.outlines if re.search(r"test_b\.py\s+[.Fs]+", line)]
        assert len(a_lines) == 1, (
            f"Expected test_a.py on 1 result line, got {len(a_lines)}: "
            f"{a_lines}\nstdout:\n{result.stdout}"
        )
        assert len(b_lines) == 1, (
            f"Expected test_b.py on 1 result line, got {len(b_lines)}: "
            f"{b_lines}\nstdout:\n{result.stdout}"
        )

    def test_no_ansi_escapes(self, ftdir):
        """Dumb mode output contains no ANSI escape sequences."""
        _setup_multi_file_pkg(ftdir)
        result = ftdir.run_pytest("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        ansi_lines = [line for line in result.outlines if re.search(r"\033[\[\]]", line)]
        assert not ansi_lines, "ANSI escapes found in dumb mode output:\n" + "\n".join(ansi_lines)

    def test_progress_on_file_lines(self, ftdir):
        """Each file line includes a progress percentage."""
        _setup_multi_file_pkg(ftdir)
        result = ftdir.run_pytest("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        file_lines = [line for line in result.outlines if _RESULT_LINE_RE.search(line)]
        assert len(file_lines) == 2, (
            f"Expected 2 result lines, got {len(file_lines)}: "
            f"{file_lines}\nstdout:\n{result.stdout}"
        )
        for line in file_lines:
            assert re.search(r"\[\s*\d+%\]", line), f"Missing progress on file line: {line!r}"


class TestLiveMode:
    """Verify output in live/TTY mode (PTY subprocess)."""

    def test_contains_ansi_cursor_movement(self, ftdir):
        """Live mode uses ANSI cursor-up sequences for in-place updates."""
        _setup_multi_file_pkg(ftdir)
        result = ftdir.run_pytest_tty("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        # Cursor-up escape: ESC[nA
        assert re.search(r"\033\[\d+A", result.stdout), (
            f"No cursor-up ANSI sequences in live mode output.\nstdout:\n{result.stdout!r}"
        )

    def test_progress_line_at_end(self, ftdir):
        """Live mode has a single progress summary line (N/N [100%])."""
        _setup_multi_file_pkg(ftdir)
        result = ftdir.run_pytest_tty("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        screen = _render_terminal(result.stdout)
        progress_lines = [line for line in screen if re.search(r"4/4\s*\[\s*100%\]", line)]
        assert progress_lines, "No '4/4 [100%]' progress line found.\nscreen:\n" + "\n".join(
            screen
        )

    def test_file_lines_no_per_line_progress(self, ftdir):
        """File lines in live mode do not have individual percentages."""
        _setup_multi_file_pkg(ftdir)
        result = ftdir.run_pytest_tty("--freethreaded", "4")
        result.assert_outcomes(passed=4)

        screen = _render_terminal(result.stdout)
        for line in screen:
            if _RESULT_LINE_RE.search(line):
                assert not re.search(r"\[\s*\d+%\]", line), (
                    f"File line has per-line progress: {line!r}"
                )
