"""Conftest for pytest-threadpool plugin tests."""

import os
import re
import select
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CASES_DIR = Path(__file__).parent / "cases"
PROJECT_ROOT = Path(__file__).parent.parent.parent
PYPROJECT_TOML = str(PROJECT_ROOT / "pyproject.toml")


class RunResult:
    """Parsed result from a subprocess pytest run."""

    def __init__(self, stdout, stderr, returncode):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.outlines = stdout.splitlines()

    @property
    def collected(self):
        """Parse the 'collected N items' count from pytest output."""
        for line in self.outlines:
            m = re.search(r"collected (\d+) items?", line)
            if m:
                return int(m.group(1))
        return None

    def assert_outcomes(self, **expected):
        all_keys = {"passed", "failed", "errors", "skipped", "xfailed", "xpassed"}
        defaults = dict.fromkeys(all_keys, 0)
        defaults.update(expected)
        # Parse "X passed, Y failed, ..." from the summary line
        # Use singular forms too (pytest prints "1 error" not "1 errors")
        _singular = {"errors": "errors?"}
        outcomes = dict.fromkeys(all_keys, 0)
        for line in reversed(self.outlines):
            for key in outcomes:
                pat = _singular.get(key, key)
                m = re.search(rf"(\d+) {pat}", line)
                if m:
                    outcomes[key] = int(m.group(1))
            if any(k in line for k in outcomes):
                break
        assert outcomes == defaults, (
            f"Expected {defaults}, got {outcomes}\nstdout:\n{self.stdout}\nstderr:\n{self.stderr}"
        )


class FreethreadedTestDir:
    """Thread-safe test directory for running pytest subprocesses.

    Unlike pytester, this does not call os.chdir() so it is safe
    to use from multiple threads concurrently.
    """

    def __init__(self, path):
        self.path = path

    def copy_case(self, case_name):
        """Copy a case file from tests/cases/ into the test directory.

        The case file is renamed to test_case.py so pytest collects it.
        """
        src = CASES_DIR / f"{case_name}.py"
        dst = self.path / "test_case.py"
        shutil.copy2(src, dst)
        return dst

    def makepyfile(self, source, name="test_file"):
        """Write a .py file into the test directory."""
        import textwrap

        p = self.path / f"{name}.py"
        p.write_text(textwrap.dedent(source))
        return p

    def mkdir(self, name):
        """Create a subdirectory."""
        d = self.path / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _coverage_env():
        """Build env dict for subprocess coverage collection.

        When the outer test suite is running under coverage (COVERAGE_PROCESS_START
        is set, or pytest-cov is active), propagate the setting so the child
        subprocess writes its own .coverage data file.  COVERAGE_FILE is set
        to the project root so all parallel data files land in one directory.
        """
        env = os.environ.copy()
        # Prevent teamcity-messages from auto-activating in child processes
        # unless the test explicitly passes --teamcity.
        env.pop("TEAMCITY_VERSION", None)
        if os.getenv("COVERAGE_PROCESS_START"):
            # Resolve to absolute path so subprocess finds config from its cwd
            env["COVERAGE_PROCESS_START"] = str(
                Path(os.environ["COVERAGE_PROCESS_START"]).resolve()
            )
            env.setdefault("COVERAGE_FILE", str(PROJECT_ROOT / ".coverage"))
        return env

    def run_pytest(self, *extra_args, timeout=30):
        """Run pytest in a subprocess (piped, non-TTY)."""
        args = [
            sys.executable,
            "-m",
            "pytest",
            str(self.path),
            "--basetemp",
            str(self.path / ".tmp"),
            *extra_args,
        ]
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(self.path),
            env=self._coverage_env(),
        )
        return RunResult(result.stdout, result.stderr, result.returncode)

    def run_pytest_tty(self, *extra_args, timeout=30):
        """Run pytest in a PTY so the child sees a real terminal.

        Returns a RunResult whose stdout contains ANSI escape sequences
        exactly as a user would see them.
        """
        import pty

        args = [
            sys.executable,
            "-m",
            "pytest",
            str(self.path),
            "--basetemp",
            str(self.path / ".tmp"),
            *extra_args,
        ]
        master_fd, slave_fd = pty.openpty()
        env = self._coverage_env()
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "120"
        proc = subprocess.Popen(
            args,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(self.path),
            env=env,
            close_fds=True,
        )
        os.close(slave_fd)

        chunks = []
        while True:
            try:
                ready, _, _ = select.select([master_fd], [], [], timeout)
                if not ready:
                    proc.kill()
                    break
                data = os.read(master_fd, 4096)
                if not data:
                    break
                chunks.append(data)
            except OSError:
                break
        os.close(master_fd)
        proc.wait(timeout=5)

        raw = b"".join(chunks).decode("utf-8", errors="replace")
        return RunResult(raw, "", proc.returncode)


@pytest.fixture
def ftdir(tmp_path):
    """Thread-safe test directory fixture for running pytest subprocesses."""
    return FreethreadedTestDir(tmp_path)
