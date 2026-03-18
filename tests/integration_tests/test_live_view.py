"""Integration tests for the live-view interface wrapper (--threadpool-output)."""

import os
import pty
import select
import signal
import subprocess
import sys
import time

SIMPLE_TESTS = """\
import pytest

@pytest.mark.parallelizable("children")
class TestSimple:
    def test_a(self):
        pass

    def test_b(self):
        pass

    def test_c(self):
        pass
"""


def _run_live_pty(ftdir, *, wait_for="Ctrl+C", send_sigint=True):
    """Run pytest with --threadpool-output=live in a PTY.

    Reads output until ``wait_for`` appears, optionally sends SIGINT,
    drains remaining output, and returns (raw_output, returncode).
    """
    args = [
        sys.executable,
        "-m",
        "pytest",
        str(ftdir.path),
        "--basetemp",
        str(ftdir.path / ".tmp"),
        "--threadpool",
        "3",
        "--threadpool-output",
        "live",
    ]
    master_fd, slave_fd = pty.openpty()
    env = os.environ.copy()
    env.pop("TEAMCITY_VERSION", None)
    env["TERM"] = "xterm-256color"
    env["COLUMNS"] = "120"
    proc = subprocess.Popen(
        args,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(ftdir.path),
        env=env,
        close_fds=True,
    )
    os.close(slave_fd)

    chunks = []
    deadline = time.monotonic() + 20
    found = False
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.5)
        if ready:
            try:
                data = os.read(master_fd, 4096)
                if not data:
                    break
                chunks.append(data)
                combined = b"".join(chunks).decode("utf-8", errors="replace")
                if wait_for in combined:
                    found = True
                    break
            except OSError:
                break

    still_alive = proc.poll() is None

    if send_sigint and still_alive:
        # Brief pause to ensure the child's signal handler is installed
        # before SIGINT arrives (the prompt text may be flushed to the
        # PTY before the handler is fully registered).
        time.sleep(0.1)
        proc.send_signal(signal.SIGINT)

    # Drain remaining output
    exit_deadline = time.monotonic() + 10
    while time.monotonic() < exit_deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.5)
        if ready:
            try:
                data = os.read(master_fd, 4096)
                if not data:
                    break
                chunks.append(data)
            except OSError:
                break
        if proc.poll() is not None:
            break

    os.close(master_fd)
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)
    else:
        proc.wait(timeout=5)

    raw = b"".join(chunks).decode("utf-8", errors="replace")
    return raw, proc.returncode, found, still_alive


class TestLiveViewClassicMode:
    """--threadpool-output=classic behaves identically to the default."""

    def test_classic_same_as_default(self, ftdir):
        """Classic mode produces identical results to running without the flag."""
        ftdir.makepyfile(SIMPLE_TESTS)
        result_default = ftdir.run_pytest("--threadpool", "3")
        result_classic = ftdir.run_pytest("--threadpool", "3", "--threadpool-output", "classic")

        result_default.assert_outcomes(passed=3)
        result_classic.assert_outcomes(passed=3)

    def test_classic_no_wait(self, ftdir):
        """Classic mode exits immediately without waiting for Ctrl+C."""
        ftdir.makepyfile(SIMPLE_TESTS)
        result = ftdir.run_pytest(
            "--threadpool", "3", "--threadpool-output", "classic", timeout=10
        )
        result.assert_outcomes(passed=3)
        assert result.returncode == 0


class TestLiveViewLiveMode:
    """--threadpool-output=live keeps the view alive until Ctrl+C."""

    def test_live_stays_alive_until_sigint(self, ftdir):
        """Live mode process stays running after tests complete until SIGINT."""
        ftdir.makepyfile(SIMPLE_TESTS)
        raw, rc, found_msg, was_alive = _run_live_pty(ftdir)

        assert found_msg, f"Did not see 'Ctrl+C' prompt in output.\nstdout: {raw}"
        assert was_alive, "Live mode process exited before SIGINT was sent"
        assert rc == 0, f"Live mode exit code: {rc}\nstdout: {raw}"

    def test_live_output_contains_results(self, ftdir):
        """Live mode shows test results before the wait prompt."""
        ftdir.makepyfile(SIMPLE_TESTS)
        raw, _rc, found_msg, _ = _run_live_pty(ftdir)

        assert found_msg, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        assert "3 passed" in raw, f"Live mode missing '3 passed' in output:\n{raw}"

    def test_live_output_matches_classic(self, ftdir):
        """Live mode produces the same test outcomes as classic mode."""
        ftdir.makepyfile(SIMPLE_TESTS)

        result_classic = ftdir.run_pytest("--threadpool", "3", "--threadpool-output", "classic")
        result_classic.assert_outcomes(passed=3)

        raw, _rc, _, _ = _run_live_pty(ftdir)
        assert "3 passed" in raw, f"Live mode missing '3 passed' in output:\n{raw}"


class TestLiveViewOptionValidation:
    """Verify the --threadpool-output option is properly validated."""

    def test_invalid_choice_rejected(self, ftdir):
        """Invalid --threadpool-output value is rejected by argparse."""
        ftdir.makepyfile(SIMPLE_TESTS)
        result = ftdir.run_pytest("--threadpool", "3", "--threadpool-output", "bogus")
        assert result.returncode != 0
        assert (
            "invalid choice" in result.stderr.lower() or "invalid choice" in result.stdout.lower()
        )

    def test_classic_is_default(self, ftdir):
        """When --threadpool-output is not specified, classic mode is used."""
        ftdir.makepyfile(SIMPLE_TESTS)
        result = ftdir.run_pytest("--threadpool", "3", timeout=10)
        result.assert_outcomes(passed=3)
        assert result.returncode == 0
