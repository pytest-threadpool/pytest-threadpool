"""Tests for stdout capture and stream proxy behavior during parallel execution."""

import re


class TestDefaultCapture:
    """Worker print() output is suppressed by default (stream proxy active)."""

    def test_worker_print_suppressed_dumb(self, ftdir):
        """In default capture mode, worker print() does not appear in stdout."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest("--threadpool", "4")
        result.assert_outcomes(passed=4)

        for line in result.outlines:
            assert "WORKER_OUTPUT" not in line, (
                f"Worker print() leaked into output: {line!r}\nstdout:\n{result.stdout}"
            )

    def test_worker_print_suppressed_tty(self, ftdir):
        """In default capture mode with TTY, worker print() does not appear."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest_tty("--threadpool", "4")
        result.assert_outcomes(passed=4)

        clean = re.sub(r"\033\[[^a-zA-Z]*[a-zA-Z]", "", result.stdout)
        assert "WORKER_OUTPUT" not in clean, (
            f"Worker print() leaked into TTY output.\nstdout:\n{result.stdout}"
        )

    def test_two_groups_suppressed(self, ftdir):
        """Worker print() from both parallel groups is suppressed."""
        ftdir.copy_case("capture_two_groups")
        result = ftdir.run_pytest("--threadpool", "4")
        result.assert_outcomes(passed=7)

        for line in result.outlines:
            assert "GROUP_A_OUTPUT" not in line, (
                f"Group A print() leaked: {line!r}\nstdout:\n{result.stdout}"
            )
            assert "GROUP_B_OUTPUT" not in line, (
                f"Group B print() leaked: {line!r}\nstdout:\n{result.stdout}"
            )

    def test_sequential_print_captured_normally(self, ftdir):
        """Sequential test print() is captured by pytest normally (not by stream proxy)."""
        ftdir.copy_case("capture_two_groups")
        result = ftdir.run_pytest("--threadpool", "4")
        result.assert_outcomes(passed=7)

        # Sequential output should NOT appear in stdout (pytest captures it)
        for line in result.outlines:
            assert "SEQ_OUTPUT" not in line or "PASSED" in line or "Captured" in line, (
                f"Unexpected sequential output: {line!r}\nstdout:\n{result.stdout}"
            )


class TestCaptureNoFlag:
    """With -s (--capture=no), worker output is captured and reported
    alongside test results (in 'Captured stdout call' sections)."""

    def test_worker_print_visible_with_dash_s(self, ftdir):
        """With -s, worker print() output appears in stdout (captured section)."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "-s")
        result.assert_outcomes(passed=4)

        assert "WORKER_OUTPUT" in result.stdout, (
            f"Worker print() should be visible with -s.\nstdout:\n{result.stdout}"
        )

    def test_all_workers_visible_with_dash_s(self, ftdir):
        """With -s, output from all workers appears."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "-s")
        result.assert_outcomes(passed=4)

        for i in range(4):
            assert f"WORKER_OUTPUT_{i}" in result.stdout, (
                f"Missing output from worker {i} with -s.\nstdout:\n{result.stdout}"
            )

    def test_capture_no_long_form(self, ftdir):
        """--capture=no has the same effect as -s."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--capture=no")
        result.assert_outcomes(passed=4)

        assert "WORKER_OUTPUT" in result.stdout, (
            f"Worker print() should be visible with --capture=no.\nstdout:\n{result.stdout}"
        )

    def test_two_groups_visible_with_dash_s(self, ftdir):
        """With -s, print() from both parallel groups appears."""
        ftdir.copy_case("capture_two_groups")
        result = ftdir.run_pytest("--threadpool", "4", "-s")
        result.assert_outcomes(passed=7)

        assert "GROUP_A_OUTPUT" in result.stdout, (
            f"Group A output missing with -s.\nstdout:\n{result.stdout}"
        )
        assert "GROUP_B_OUTPUT" in result.stdout, (
            f"Group B output missing with -s.\nstdout:\n{result.stdout}"
        )
        assert "SEQ_OUTPUT" in result.stdout, (
            f"Sequential output missing with -s.\nstdout:\n{result.stdout}"
        )


class TestPassiveMode:
    """With -s in a non-TTY subprocess, the reporter is passive.

    The terminal reporter's per-test output (PASSED/FAILED) is
    suppressed during parallel reporting.  IDE test runners
    (TeamCity / PyCharm) write directly to sys.stdout and are
    unaffected by the suppression.
    """

    def test_captured_output_emitted_with_dash_s(self, ftdir):
        """With -s, captured worker output appears in stdout."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "-s")
        result.assert_outcomes(passed=4)

        assert "WORKER_OUTPUT" in result.stdout, (
            f"Worker output should appear in stdout.\nstdout:\n{result.stdout}"
        )

    def test_no_custom_reporter_lines_with_dash_s(self, ftdir):
        """With -s, the custom dumb-mode reporter does not write file lines."""
        _INIT = 'import pytest\npytestmark = pytest.mark.parallelizable("children")\n'
        _MOD_A = "def test_a1(): pass\ndef test_a2(): pass\n"
        _MOD_B = "def test_b1(): pass\ndef test_b2(): pass\n"
        pkg = ftdir.mkdir("spkg")
        pkg.joinpath("__init__.py").write_text(_INIT)
        pkg.joinpath("test_a.py").write_text(_MOD_A)
        pkg.joinpath("test_b.py").write_text(_MOD_B)

        result = ftdir.run_pytest("--threadpool", "4", "-s")
        result.assert_outcomes(passed=4)

        # Custom dumb-mode lines have format "path ..  [ xx%]" with progress.
        # In passive mode, these should not appear — pytest's standard output
        # handles everything.
        custom_lines = [
            line
            for line in result.outlines
            if re.search(r"test_[ab]\.py\s+\.+\s+\[\s*\d+%\]", line)
        ]
        assert not custom_lines, (
            f"Custom reporter lines found in passive mode: {custom_lines}\n"
            f"stdout:\n{result.stdout}"
        )


class TestGroupSeparation:
    """Newline separation between consecutive parallel groups."""

    def test_newline_between_groups_dumb(self, ftdir):
        """In dumb mode, each parallel group's file line starts on its own line."""
        ftdir.copy_case("capture_two_groups")
        result = ftdir.run_pytest("--threadpool", "4")
        result.assert_outcomes(passed=7)

        # The key check: no two result lines should be on the same output line
        result_lines = [
            line for line in result.outlines if re.search(r"test_case\.py\s+[.Fs]+", line)
        ]
        # With two groups from the same file, we should have at least 1 result line
        # (or 2 if groups produce separate lines — depends on grouping).
        # The main check: no garbled output where groups run together.
        for line in result_lines:
            # A result line should not contain two separate file references
            parts = re.findall(r"test_case\.py", line)
            assert len(parts) <= 1, (
                f"Groups merged onto one line: {line!r}\nstdout:\n{result.stdout}"
            )

    def test_no_result_line_overlap(self, ftdir):
        """Result lines from different groups don't overlap in dumb mode."""
        _INIT = 'import pytest\npytestmark = pytest.mark.parallelizable("children")\n'
        _MOD_A = (
            "import time\n\n"
            "class TestA:\n"
            "    def test_a1(self):\n"
            "        print('A1_OUT')\n"
            "    def test_a2(self):\n"
            "        print('A2_OUT')\n"
        )
        _MOD_B = (
            "import time\n\n"
            "class TestB:\n"
            "    def test_b1(self):\n"
            "        print('B1_OUT')\n"
            "    def test_b2(self):\n"
            "        print('B2_OUT')\n"
        )
        pkg = ftdir.mkdir("cappkg")
        pkg.joinpath("__init__.py").write_text(_INIT)
        pkg.joinpath("test_a.py").write_text(_MOD_A)
        pkg.joinpath("test_b.py").write_text(_MOD_B)

        result = ftdir.run_pytest("--threadpool", "4")
        result.assert_outcomes(passed=4)

        # Worker output should be suppressed
        for line in result.outlines:
            assert "A1_OUT" not in line, f"Leaked: {line!r}\nstdout:\n{result.stdout}"
            assert "B1_OUT" not in line, f"Leaked: {line!r}\nstdout:\n{result.stdout}"

        # Each module should appear on exactly one result line
        a_lines = [line for line in result.outlines if re.search(r"test_a\.py\s+[.Fs]+", line)]
        b_lines = [line for line in result.outlines if re.search(r"test_b\.py\s+[.Fs]+", line)]
        assert len(a_lines) == 1, (
            f"Expected test_a.py on 1 line, got {len(a_lines)}\nstdout:\n{result.stdout}"
        )
        assert len(b_lines) == 1, (
            f"Expected test_b.py on 1 line, got {len(b_lines)}\nstdout:\n{result.stdout}"
        )
