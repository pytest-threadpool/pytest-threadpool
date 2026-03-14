"""Conftest for pytest-freethreaded plugin tests."""

import subprocess
import sys
import re

import pytest


class RunResult:
    """Parsed result from a subprocess pytest run."""

    def __init__(self, stdout, stderr, returncode):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.outlines = stdout.splitlines()

    def assert_outcomes(self, **expected):
        defaults = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        defaults.update(expected)
        # Parse "X passed, Y failed, ..." from the summary line
        outcomes = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        for line in reversed(self.outlines):
            for key in outcomes:
                m = re.search(rf"(\d+) {key}", line)
                if m:
                    outcomes[key] = int(m.group(1))
            if any(k in line for k in outcomes):
                break
        assert outcomes == defaults, (
            f"Expected {defaults}, got {outcomes}\n"
            f"stdout:\n{self.stdout}\n"
            f"stderr:\n{self.stderr}"
        )


class FreethreadedTestDir:
    """Thread-safe test directory for running pytest subprocesses.

    Unlike pytester, this does not call os.chdir() so it is safe
    to use from multiple threads concurrently.
    """

    def __init__(self, path):
        self.path = path

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

    def run_pytest(self, *extra_args, timeout=30):
        """Run pytest in a subprocess against this directory."""
        args = [
            sys.executable, "-m", "pytest",
            str(self.path),
            "--basetemp", str(self.path / ".tmp"),
            *extra_args,
        ]
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(self.path),
        )
        return RunResult(result.stdout, result.stderr, result.returncode)


@pytest.fixture
def ftdir(tmp_path):
    """Thread-safe test directory fixture for running pytest subprocesses."""
    return FreethreadedTestDir(tmp_path)
