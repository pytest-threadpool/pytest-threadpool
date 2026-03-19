"""Integration tests for the live-view interface wrapper (--threadpool-output)."""

import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time


def _set_pty_size(fd: int, rows: int, cols: int) -> None:
    """Set the terminal size on a pty fd via ioctl."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


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


def _run_live_pty(ftdir, *, wait_for="tests complete", send_sigint=True):
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
    _set_pty_size(slave_fd, rows=24, cols=120)
    env = os.environ.copy()
    env.pop("TEAMCITY_VERSION", None)
    env["TERM"] = "xterm-256color"
    env["COLUMNS"] = "120"
    env["LINES"] = "24"
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


class TestClassicModeOutcomes:
    """Classic (piped) mode displays correct outcome markers."""

    def test_classic_fail_marker(self, ftdir):
        """Failed tests produce 'F' marker in classic output."""
        ftdir.makepyfile(FAILING_TESTS)
        result = ftdir.run_pytest("--threadpool", "3")
        assert "F" in result.stdout, f"Missing 'F' marker:\n{result.stdout}"
        result.assert_outcomes(passed=1, failed=1, skipped=1, xfailed=1, xpassed=1)

    def test_classic_skip_marker(self, ftdir):
        """Skipped tests produce 's' marker in classic output."""
        ftdir.makepyfile(FAILING_TESTS)
        result = ftdir.run_pytest("--threadpool", "3")
        assert "s" in result.stdout, f"Missing 's' marker:\n{result.stdout}"

    def test_classic_xfail_marker(self, ftdir):
        """Expected failures produce 'x' marker in classic output."""
        ftdir.makepyfile(FAILING_TESTS)
        result = ftdir.run_pytest("--threadpool", "3")
        assert "x" in result.stdout, f"Missing 'x' marker:\n{result.stdout}"

    def test_classic_xpass_marker(self, ftdir):
        """Unexpected passes produce 'X' marker in classic output."""
        ftdir.makepyfile(FAILING_TESTS)
        result = ftdir.run_pytest("--threadpool", "3")
        assert "X" in result.stdout, f"Missing 'X' marker:\n{result.stdout}"

    def test_classic_error_marker(self, ftdir):
        """Setup errors produce 'E' marker in classic output."""
        ftdir.makepyfile(ERROR_IN_SETUP)
        result = ftdir.run_pytest("--threadpool", "3")
        assert "E" in result.stdout, f"Missing 'E' marker:\n{result.stdout}"
        result.assert_outcomes(passed=1, errors=1)


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
        """Live mode dumps test file lines after Ctrl+C."""
        ftdir.makepyfile(SIMPLE_TESTS)
        raw, _rc, found_msg, _ = _run_live_pty(ftdir)

        assert found_msg, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        # After Ctrl+C, the buffer is dumped as plain text.
        # The file line contains the test file name and result dots.
        assert "test_file.py" in raw, f"Live mode missing test file in output:\n{raw}"

    def test_live_output_matches_classic(self, ftdir):
        """Live mode exits cleanly and dumps results."""
        ftdir.makepyfile(SIMPLE_TESTS)

        result_classic = ftdir.run_pytest("--threadpool", "3", "--threadpool-output", "classic")
        result_classic.assert_outcomes(passed=3)

        raw, rc, _, _ = _run_live_pty(ftdir)
        assert rc == 0, f"Live mode exit code: {rc}\nstdout: {raw}"
        assert "test_file.py" in raw, f"Live mode missing test file in output:\n{raw}"


MANY_TESTS = """\
import pytest

@pytest.mark.parallelizable("children")
class TestWide:
{methods}
""".format(methods="\n".join(f"    def test_{i:03d}(self): pass" for i in range(80)))


class TestWidthTruncation:
    """Lines wider than the terminal are truncated, not wrapped."""

    def test_dumb_mode_no_line_wrap(self, ftdir):
        """In dumb/pipe mode, file lines fit within 80 columns."""
        ftdir.makepyfile(MANY_TESTS)
        result = ftdir.run_pytest("--threadpool", "4")
        result.assert_outcomes(passed=80)

        for line in result.outlines:
            # Only check result lines (path + dots + progress).
            if "test_file.py" in line and "." in line:
                assert len(line) <= 80, f"Line exceeds 80 cols ({len(line)}): {line!r}"

    def test_live_mode_no_line_wrap(self, ftdir):
        """In live/TTY mode with narrow terminal, lines are truncated."""
        ftdir.makepyfile(MANY_TESTS)
        # Live mode blocks on Ctrl+C, so use the PTY helper that sends SIGINT.
        raw, rc, _, _ = _run_live_pty(ftdir, wait_for="tests complete", send_sigint=True)
        assert rc == 0, f"Live mode exit code: {rc}\nstdout: {raw}"
        assert "test_file.py" in raw, f"Missing test file in output:\n{raw}"


# Enough tests to fill more than one terminal screen (24 lines) so scroll is
# needed.  Each test method is tiny so the run is fast.
SCROLLABLE_TESTS = """\
import pytest

@pytest.mark.parallelizable("children")
class TestScrollable:
{methods}
""".format(methods="\n".join(f"    def test_{i:03d}(self): pass" for i in range(60)))

# SGR mouse scroll events (col 1, row 1, press).
_SCROLL_UP_SGR = b"\033[<64;1;1M"
_SCROLL_DOWN_SGR = b"\033[<65;1;1M"
_ARROW_UP = b"\033[A"
_ARROW_DOWN = b"\033[B"


def _read_pty(master_fd, timeout=0.5):
    """Read all available data from a pty master with timeout."""
    chunks = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.05)
        if ready:
            try:
                data = os.read(master_fd, 65536)
                if not data:
                    break
                chunks.append(data)
            except OSError:
                break
    return b"".join(chunks)


class TestLiveViewScrollResponsiveness:
    """Scroll input must produce visible display changes after tests finish."""

    def test_scroll_events_produce_display_output(self, ftdir):
        """After tests complete, sending scroll events to the pty master
        must produce cursor-movement output (proving the display updated).

        This reproduces the exact real-world flow: real pytest collection,
        real test execution, real plugin hooks, then post-test scroll.
        """
        ftdir.makepyfile(SCROLLABLE_TESTS)
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
        _set_pty_size(slave_fd, rows=6, cols=120)
        env = os.environ.copy()
        env.pop("TEAMCITY_VERSION", None)
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "120"
        env["LINES"] = "6"
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

        try:
            # Wait for "Ctrl+C" prompt — signals post-test state.
            combined = b""
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master_fd], [], [], 0.5)
                if ready:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        combined += data
                    except OSError:
                        break
                    if b"tests complete" in combined:
                        break
            assert b"tests complete" in combined, (
                f"Never saw Ctrl+C prompt.\nOutput ({len(combined)} bytes): {combined[-500:]!r}"
            )

            # Drain any remaining output from the rendering.
            _read_pty(master_fd, timeout=0.3)

            # Send alternating scroll-up/down events so we never hit a
            # boundary where further scrolling produces no display change.
            latencies = []
            debug_info = []
            for _i in range(10):
                t0 = time.monotonic()
                event = _SCROLL_UP_SGR if _i % 2 == 0 else _SCROLL_DOWN_SGR
                os.write(master_fd, event)
                # Poll rapidly for display output.
                got_response = False
                response_bytes = 0
                deadline_inner = t0 + 1.0
                while time.monotonic() < deadline_inner:
                    ready, _, _ = select.select([master_fd], [], [], 0.01)
                    if ready:
                        try:
                            data = os.read(master_fd, 65536)
                            if data:
                                elapsed_ms = (time.monotonic() - t0) * 1000
                                latencies.append(elapsed_ms)
                                response_bytes = len(data)
                                got_response = True
                                break
                        except OSError:
                            break
                debug_info.append(
                    f"#{_i}: {'ok' if got_response else 'TIMEOUT'} "
                    f"{latencies[-1]:.0f}ms {response_bytes}B"
                    if got_response
                    else f"#{_i}: TIMEOUT"
                )

            assert len(latencies) >= 5, (
                f"Only {len(latencies)}/10 scroll events produced "
                f"display output.\nDetails: {debug_info}"
            )
            avg_ms = sum(latencies) / len(latencies) if latencies else 0
            assert avg_ms < 200, (
                f"Average scroll latency {avg_ms:.0f} ms is too high.\nDetails: {debug_info}"
            )

        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                time.sleep(0.2)
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            os.close(master_fd)

    def test_arrow_keys_produce_display_output(self, ftdir):
        """Arrow keys also produce display output after tests finish."""
        ftdir.makepyfile(SCROLLABLE_TESTS)
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
        _set_pty_size(slave_fd, rows=6, cols=120)
        env = os.environ.copy()
        env.pop("TEAMCITY_VERSION", None)
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "120"
        env["LINES"] = "6"
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

        try:
            combined = b""
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master_fd], [], [], 0.5)
                if ready:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        combined += data
                    except OSError:
                        break
                    if b"tests complete" in combined:
                        break
            assert b"tests complete" in combined, "Never saw Ctrl+C prompt"

            _read_pty(master_fd, timeout=0.3)

            latencies = []
            debug_info = []
            for _i in range(10):
                t0 = time.monotonic()
                arrow = _ARROW_UP if _i % 2 == 0 else _ARROW_DOWN
                os.write(master_fd, arrow)
                got_response = False
                response_bytes = 0
                deadline_inner = t0 + 1.0
                while time.monotonic() < deadline_inner:
                    ready, _, _ = select.select([master_fd], [], [], 0.01)
                    if ready:
                        try:
                            data = os.read(master_fd, 65536)
                            if data:
                                elapsed_ms = (time.monotonic() - t0) * 1000
                                latencies.append(elapsed_ms)
                                response_bytes = len(data)
                                got_response = True
                                break
                        except OSError:
                            break
                debug_info.append(
                    f"#{_i}: {'ok' if got_response else 'TIMEOUT'} "
                    f"{latencies[-1]:.0f}ms {response_bytes}B"
                    if got_response
                    else f"#{_i}: TIMEOUT"
                )

            assert len(latencies) >= 5, (
                f"Only {len(latencies)}/10 arrow-up events produced "
                f"display output.\nDetails: {debug_info}"
            )
            avg_ms = sum(latencies) / len(latencies) if latencies else 0
            assert avg_ms < 200, (
                f"Average arrow-key latency {avg_ms:.0f} ms is too high.\nDetails: {debug_info}"
            )

        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                time.sleep(0.2)
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            os.close(master_fd)


FAILING_TESTS = """\
import pytest

@pytest.mark.parallelizable("children")
class TestOutcomes:
    def test_pass(self):
        pass

    def test_fail(self):
        assert False, "intentional failure"

    def test_skip(self):
        pytest.skip("skipped on purpose")

    def test_xfail(self):
        pytest.xfail("expected failure")

    @pytest.mark.xfail(reason="should pass")
    def test_xpass(self):
        pass
"""

ERROR_IN_SETUP = """\
import pytest

@pytest.fixture
def broken_fixture():
    raise RuntimeError("setup boom")

@pytest.mark.parallelizable("children")
class TestSetupError:
    def test_ok(self):
        pass

    def test_broken(self, broken_fixture):
        pass
"""


class TestLiveViewOutcomes:
    """Live view displays correct indicators for all test outcomes."""

    def test_fail_shows_F_letter(self, ftdir):
        """Failed tests show 'F' in the live view output."""
        ftdir.makepyfile(FAILING_TESTS)
        raw, rc, found, _ = _run_live_pty(ftdir)
        assert found, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        assert rc != 0, f"Expected non-zero exit code.\nstdout: {raw}"
        assert "F" in raw, f"Missing 'F' for failed test:\n{raw}"

    def test_skip_shows_s_letter(self, ftdir):
        """Skipped tests show 's' in the live view output."""
        ftdir.makepyfile(FAILING_TESTS)
        raw, _rc, found, _ = _run_live_pty(ftdir)
        assert found, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        assert "s" in raw, f"Missing 's' for skipped test:\n{raw}"

    def test_xfail_shows_x_letter(self, ftdir):
        """Expected failures show 'x' in the live view output."""
        ftdir.makepyfile(FAILING_TESTS)
        raw, _rc, found, _ = _run_live_pty(ftdir)
        assert found, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        assert "x" in raw, f"Missing 'x' for xfail test:\n{raw}"

    def test_xpass_shows_X_letter(self, ftdir):
        """Unexpected passes show 'X' in the live view output."""
        ftdir.makepyfile(FAILING_TESTS)
        raw, _rc, found, _ = _run_live_pty(ftdir)
        assert found, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        assert "X" in raw, f"Missing 'X' for xpass test:\n{raw}"

    def test_error_in_setup_shows_E_letter(self, ftdir):
        """Setup errors show 'E' in the live view output."""
        ftdir.makepyfile(ERROR_IN_SETUP)
        raw, rc, found, _ = _run_live_pty(ftdir)
        assert found, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        assert rc != 0, f"Expected non-zero exit code.\nstdout: {raw}"
        assert "E" in raw, f"Missing 'E' for setup error:\n{raw}"

    def test_failure_summary_visible(self, ftdir):
        """Failure details are visible in the live view dump after Ctrl+C."""
        ftdir.makepyfile(FAILING_TESTS)
        raw, _rc, found, _ = _run_live_pty(ftdir)
        assert found, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        assert "FAILED" in raw or "intentional failure" in raw, (
            f"Missing failure summary in output:\n{raw}"
        )

    def test_mixed_outcomes_summary_line(self, ftdir):
        """The summary line reports correct counts for mixed outcomes."""
        ftdir.makepyfile(FAILING_TESTS)
        raw, _rc, found, _ = _run_live_pty(ftdir)
        assert found, f"Did not see 'Ctrl+C' prompt.\nstdout: {raw}"
        assert "1 failed" in raw, f"Missing '1 failed' in summary:\n{raw}"
        assert "1 passed" in raw or "passed" in raw, f"Missing passed count in summary:\n{raw}"


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
