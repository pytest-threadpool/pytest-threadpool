"""Tests for error and edge-case scenarios during parallel execution."""

import shutil
import signal
import subprocess
import sys
import time

from tests.integration_tests.conftest import CASES_DIR


def _run_and_sigint(ftdir, *, threads="3"):
    """Launch pytest in a subprocess, wait for tests to start, then SIGINT.

    Polls for a ``.sigint_ready`` marker file that the test case writes
    once a test body begins executing, instead of using a fixed sleep.
    Returns (stdout, stderr, returncode).
    """
    ready_path = ftdir.path / ".sigint_ready"
    ready_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", str(ftdir.path), "--threadpool", threads],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(ftdir.path),
    )
    # Wait for test body to start (up to 10s)
    deadline = time.monotonic() + 10
    while not ready_path.exists():
        if time.monotonic() > deadline:
            proc.kill()
            proc.wait()
            raise AssertionError("Subprocess did not reach test body within 10s")
        time.sleep(0.05)
    proc.send_signal(signal.SIGINT)
    try:
        stdout, stderr = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        proc.wait()
        raise AssertionError(
            "Process did not exit within 10s after SIGINT — futures were not cancelled promptly"
        ) from exc
    return stdout, stderr, proc.returncode


class TestFreethreadedValidation:
    """Verify the plugin rejects --threadpool on GIL-enabled Python."""

    def test_rejects_gil_enabled_python(self, ftdir):
        """--threadpool must error when running on a GIL-enabled build."""
        ftdir.copy_case("validate_threadpool")
        # Copy the conftest that fakes sys._is_gil_enabled = True
        shutil.copy2(
            CASES_DIR / "validate_threadpool_conftest.py",
            ftdir.path / "conftest.py",
        )
        result = ftdir.run_pytest("--threadpool", "2")
        assert result.returncode != 0
        assert (
            "free-threaded Python build" in result.stderr
            or "free-threaded Python build" in result.stdout
        )


class TestSetupFailures:
    """Verify correct handling when test setup fails in parallel groups."""

    def test_all_tests_fail_setup(self, ftdir):
        """All tests in a parallel group fail during setup — no crash, all reported."""
        ftdir.copy_case("setup_all_fail")
        result = ftdir.run_pytest("--threadpool", "3")
        assert "3 error" in result.stdout
        assert "passed" not in result.stdout.split("=")[-1]

    def test_mixed_setup_pass_fail(self, ftdir):
        """Some tests pass setup, some fail — passing tests run, failures reported."""
        ftdir.copy_case("setup_mixed_pass_fail")
        result = ftdir.run_pytest("--threadpool", "3")
        assert "2 passed" in result.stdout
        assert "1 error" in result.stdout


class TestExceptionHandling:
    """Verify BaseException subclasses are handled during parallel execution."""

    def test_system_exit_in_test_body(self, ftdir):
        """SystemExit in a parallel test body is caught and reported as failure."""
        ftdir.copy_case("edge_system_exit")
        result = ftdir.run_pytest("--threadpool", "3")
        assert "1 failed" in result.stdout
        assert "2 passed" in result.stdout

    def test_keyboard_interrupt_in_test_body(self, ftdir):
        """KeyboardInterrupt in a parallel test body is caught and reported as failure."""
        ftdir.copy_case("edge_keyboard_interrupt")
        result = ftdir.run_pytest("--threadpool", "3")
        assert "1 failed" in result.stdout
        assert "2 passed" in result.stdout


class TestConcurrencyEdgeCases:
    """Verify edge cases around thread interaction."""

    def test_nested_threads(self, ftdir):
        """Tests that spawn their own threads work correctly in parallel."""
        ftdir.copy_case("edge_nested_threads")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_sigint_exits_promptly(self, ftdir):
        """SIGINT during parallel execution cancels futures and exits promptly."""
        ftdir.copy_case("edge_sigint")
        stdout, stderr, rc = _run_and_sigint(ftdir, threads="3")
        assert rc != 0
        assert "KeyboardInterrupt" in stdout or "KeyboardInterrupt" in stderr

    def test_sigint_many_threads_preserves_output(self, ftdir):
        """SIGINT with many threads must not swallow output.

        Regression: live.suppress() replaced the terminal writer with no-ops.
        If KeyboardInterrupt arrived inside the suppress window, restore()
        was skipped and pytest's interrupt traceback was silently lost.
        With many threads, results stream faster so the main thread spends
        more time in the suppress window, making this race very likely.
        """
        ftdir.copy_case("edge_sigint_many")
        stdout, stderr, rc = _run_and_sigint(ftdir, threads="20")
        assert rc != 0
        assert "KeyboardInterrupt" in stdout or "KeyboardInterrupt" in stderr


class TestCrossModuleParallelGroup:
    """Verify cross-module parallel groups complete without hanging."""

    def test_cross_module_package_group_all_complete(self, ftdir):
        """Tests from multiple modules in one package group all complete.

        Reproduces the scenario where package-level parallelizable("children")
        groups tests from different modules/classes into a single parallel batch.
        Setup/teardown of class/module collectors must not interfere with
        already-queued test items from earlier modules.
        """
        from tests.integration_tests.cases.edge_cross_module_group import (
            INIT_SRC,
            MOD_A_SRC,
            MOD_B_SRC,
            MOD_C_SRC,
        )

        pkg = ftdir.mkdir("mypkg")
        (pkg / "__init__.py").write_text(INIT_SRC)
        (pkg / "test_mod_a.py").write_text(MOD_A_SRC)
        (pkg / "test_mod_b.py").write_text(MOD_B_SRC)
        (pkg / "test_mod_c.py").write_text(MOD_C_SRC)
        result = ftdir.run_pytest("--threadpool", "4", str(pkg))
        result.assert_outcomes(passed=10)

    def test_cross_module_with_fixtures_all_complete(self, ftdir):
        """Cross-module group with yield fixtures: teardown doesn't break queued tests."""
        pkg = ftdir.mkdir("fixpkg")
        (pkg / "__init__.py").write_text(
            'import pytest\npytestmark = pytest.mark.parallelizable("children")\n'
        )
        (pkg / "conftest.py").write_text(
            "import pytest\n"
            "teardown_log = []\n"
            "\n"
            "@pytest.fixture\n"
            "def tracked(request):\n"
            "    yield request.node.name\n"
            "    teardown_log.append(request.node.name)\n"
        )
        (pkg / "test_first.py").write_text(
            "class TestFirst:\n"
            "    def test_f1(self, tracked):\n"
            "        assert tracked == 'test_f1'\n"
            "    def test_f2(self, tracked):\n"
            "        assert tracked == 'test_f2'\n"
        )
        (pkg / "test_second.py").write_text(
            "class TestSecond:\n"
            "    def test_s1(self, tracked):\n"
            "        assert tracked == 'test_s1'\n"
            "    def test_s2(self, tracked):\n"
            "        assert tracked == 'test_s2'\n"
        )
        result = ftdir.run_pytest("--threadpool", "4", str(pkg))
        result.assert_outcomes(passed=4)
