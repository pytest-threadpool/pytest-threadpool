"""Tests for IDE test runner compatibility (JetBrains TeamCity protocol).

Verifies that pytest-threadpool emits correct TeamCity service messages
when the ``teamcity-messages`` plugin is active, ensuring PyCharm and
other JetBrains IDEs can detect test results.

Also verifies output scoping in TeamCity mode: each test's ``testStdOut``
contains only its own function-level output, with shared-scope fixture
output (session/package/module/class) excluded from individual tests.

Tests cover both explicit ``--teamcity`` flag and ``TEAMCITY_VERSION``
environment variable activation (PyCharm's mechanism).
"""

import re

_SHARED_SETUP_TAGS = ("SESSION_SETUP", "PACKAGE_SETUP", "MODULE_SETUP", "CLASS_SETUP")
_SHARED_TEARDOWN_TAGS = (
    "CLASS_TEARDOWN",
    "MODULE_TEARDOWN",
    "PACKAGE_TEARDOWN",
    "SESSION_TEARDOWN",
)


def _tc_messages(stdout: str) -> list[dict[str, str]]:
    """Parse ##teamcity[...] service messages from stdout into dicts."""
    msgs = []
    for m in re.finditer(r"##teamcity\[(\w+)\s+(.*?)\]", stdout):
        name = m.group(1)
        attrs = {}
        for attr_match in re.finditer(r"(\w+)='((?:[^'|]|\|.)*)'", m.group(2)):
            key = attr_match.group(1)
            val = attr_match.group(2).replace("|n", "\n").replace("|'", "'").replace("||", "|")
            attrs[key] = val
        attrs["_type"] = name
        msgs.append(attrs)
    return msgs


def _tc_test_stdout(msgs: list[dict], test_short_name: str) -> str:
    """Concatenate all testStdOut ``out`` values for a given test name."""
    return "".join(
        m.get("out", "")
        for m in msgs
        if m["_type"] == "testStdOut" and test_short_name in m.get("name", "")
    )


# ---------------------------------------------------------------------------
# TeamCity protocol correctness
# ---------------------------------------------------------------------------


class TestTeamCityProtocol:
    """Verify TeamCity service messages are emitted for parallel tests."""

    def test_all_tests_reported(self, ftdir):
        """Each parallel test gets testStarted + testFinished messages."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--threadpool", "3", "--teamcity", "-s")
        result.assert_outcomes(passed=3)

        msgs = _tc_messages(result.stdout)
        started = [m for m in msgs if m["_type"] == "testStarted"]
        finished = [m for m in msgs if m["_type"] == "testFinished"]

        assert len(started) == 3, (
            f"Expected 3 testStarted, got {len(started)}\nstdout:\n{result.stdout}"
        )
        assert len(finished) == 3, (
            f"Expected 3 testFinished, got {len(finished)}\nstdout:\n{result.stdout}"
        )

    def test_started_before_finished(self, ftdir):
        """testStarted always precedes testFinished for the same test."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--threadpool", "3", "--teamcity", "-s")
        result.assert_outcomes(passed=3)

        msgs = _tc_messages(result.stdout)
        for fin in (m for m in msgs if m["_type"] == "testFinished"):
            name = fin["name"]
            started_idx = next(
                (
                    i
                    for i, m in enumerate(msgs)
                    if m["_type"] == "testStarted" and m["name"] == name
                ),
                None,
            )
            finished_idx = next(
                (
                    i
                    for i, m in enumerate(msgs)
                    if m["_type"] == "testFinished" and m["name"] == name
                ),
                None,
            )
            assert started_idx is not None, f"No testStarted for {name}"
            assert finished_idx is not None, f"No testFinished for {name}"
            assert started_idx < finished_idx, (
                f"testStarted after testFinished for {name}\nstdout:\n{result.stdout}"
            )

    def test_no_duplicate_messages(self, ftdir):
        """No duplicate testStarted or testFinished for the same test."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--threadpool", "3", "--teamcity", "-s")
        result.assert_outcomes(passed=3)

        msgs = _tc_messages(result.stdout)
        for msg_type in ("testStarted", "testFinished"):
            names = [m["name"] for m in msgs if m["_type"] == msg_type]
            assert len(names) == len(set(names)), (
                f"Duplicate {msg_type}: {names}\nstdout:\n{result.stdout}"
            )

    def test_no_raw_passed_in_output(self, ftdir):
        """PASSED/FAILED text from terminal reporter doesn't bleed into protocol."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--threadpool", "3", "--teamcity", "-s")
        result.assert_outcomes(passed=3)

        for line in result.outlines:
            if "##teamcity" in line:
                assert "PASSED" not in line.split("##teamcity")[0], (
                    f"PASSED bled into teamcity line: {line!r}"
                )

    def test_no_failed_messages_on_pass(self, ftdir):
        """Passing tests produce no testFailed messages."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--threadpool", "3", "--teamcity", "-s")
        result.assert_outcomes(passed=3)

        msgs = _tc_messages(result.stdout)
        failed = [m for m in msgs if m["_type"] == "testFailed"]
        assert not failed, f"Unexpected testFailed messages: {failed}\nstdout:\n{result.stdout}"

    def test_failure_reported(self, ftdir):
        """Failed tests produce testFailed messages."""
        ftdir.copy_case("scope_mixed_fail_skip")
        result = ftdir.run_pytest("--threadpool", "4", "--teamcity", "-s")

        msgs = _tc_messages(result.stdout)
        failed = [m for m in msgs if m["_type"] == "testFailed"]
        assert failed, f"Expected testFailed messages for failing tests.\nstdout:\n{result.stdout}"

    def test_test_count_message(self, ftdir):
        """testCount message is emitted with the correct count."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--threadpool", "3", "--teamcity", "-s")
        result.assert_outcomes(passed=3)

        msgs = _tc_messages(result.stdout)
        count_msgs = [m for m in msgs if m["_type"] == "testCount"]
        assert count_msgs, "No testCount message found"
        assert count_msgs[0]["count"] == "3", f"Expected count=3, got {count_msgs[0].get('count')}"


# ---------------------------------------------------------------------------
# Captured output in TeamCity messages
# ---------------------------------------------------------------------------


class TestTeamCityCapturedOutput:
    """Verify worker output appears in testStdOut and is correctly scoped."""

    def test_captured_output_in_messages(self, ftdir):
        """Worker print() output appears in testStdOut messages."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--teamcity", "-s")
        result.assert_outcomes(passed=4)

        msgs = _tc_messages(result.stdout)
        stdout_msgs = [m for m in msgs if m["_type"] == "testStdOut"]

        captured = "".join(m.get("out", "") for m in stdout_msgs)
        for i in range(4):
            assert f"WORKER_OUTPUT_{i}" in captured, (
                f"Missing WORKER_OUTPUT_{i} in testStdOut messages.\n"
                f"stdout_msgs: {stdout_msgs}\nstdout:\n{result.stdout}"
            )

    def test_test_has_only_function_output(self, ftdir):
        """testStdOut for each test has only function-scoped output (with -vs)."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs", "--teamcity")
        result.assert_outcomes(passed=5)

        msgs = _tc_messages(result.stdout)
        for test_name, call_tag in (
            ("test_alpha", "CALL_ALPHA"),
            ("test_beta", "CALL_BETA"),
            ("test_param(0)", "CALL_PARAM_0"),
            ("test_param(1)", "CALL_PARAM_1"),
            ("test_param(2)", "CALL_PARAM_2"),
        ):
            out = _tc_test_stdout(msgs, test_name)
            assert "FUNCTION_SETUP" in out, (
                f"{test_name}: missing FUNCTION_SETUP in testStdOut\nstdout:\n{result.stdout}"
            )
            assert call_tag in out, (
                f"{test_name}: missing {call_tag} in testStdOut\nstdout:\n{result.stdout}"
            )
            assert "FUNCTION_TEARDOWN" in out, (
                f"{test_name}: missing FUNCTION_TEARDOWN in testStdOut\nstdout:\n{result.stdout}"
            )

    def test_test_excludes_shared_scope(self, ftdir):
        """testStdOut for each test excludes shared-scope output (with -vs)."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs", "--teamcity")
        result.assert_outcomes(passed=5)

        msgs = _tc_messages(result.stdout)
        for test_name in ("test_alpha", "test_beta", "test_param(0)", "test_param(1)"):
            out = _tc_test_stdout(msgs, test_name)
            for tag in _SHARED_SETUP_TAGS + _SHARED_TEARDOWN_TAGS:
                assert tag not in out, (
                    f"{test_name}: {tag} leaked into testStdOut\nstdout:\n{result.stdout}"
                )

    def test_default_capture_excludes_shared_scope(self, ftdir):
        """testStdOut excludes shared-scope output in default capture mode (no -s)."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "--teamcity")
        result.assert_outcomes(passed=5)

        msgs = _tc_messages(result.stdout)
        for test_name in ("test_alpha", "test_beta", "test_param(0)", "test_param(1)"):
            out = _tc_test_stdout(msgs, test_name)
            for tag in _SHARED_SETUP_TAGS + _SHARED_TEARDOWN_TAGS:
                assert tag not in out, (
                    f"{test_name}: {tag} leaked into testStdOut (default capture)\n"
                    f"stdout:\n{result.stdout}"
                )

    def test_no_file_line_in_test_output(self, ftdir):
        """Dumb-mode file progress lines don't leak into testStdOut."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "--teamcity")
        result.assert_outcomes(passed=5)

        msgs = _tc_messages(result.stdout)
        for test_name in (
            "test_alpha",
            "test_beta",
            "test_param(0)",
            "test_param(1)",
            "test_param(2)",
        ):
            out = _tc_test_stdout(msgs, test_name)
            assert "[100%]" not in out, (
                f"{test_name}: file progress line leaked into testStdOut\nstdout:\n{result.stdout}"
            )


# ---------------------------------------------------------------------------
# TEAMCITY_VERSION env var activation (PyCharm scenario)
# ---------------------------------------------------------------------------

_TC_ENV = {"TEAMCITY_VERSION": "2024.1"}


class TestEnvVarActivation:
    """Verify TC mode activates via TEAMCITY_VERSION env var (no --teamcity flag).

    PyCharm sets TEAMCITY_VERSION instead of passing --teamcity on the CLI.
    These tests ensure pytest-threadpool detects that and enables all
    TC-specific behavior (collection-order reporting, file-line suppression,
    shared-scope output scoping).
    """

    def test_tc_messages_emitted_via_env(self, ftdir):
        """TC service messages are emitted when activated via env var."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--threadpool", "3", "-s", extra_env=_TC_ENV)
        result.assert_outcomes(passed=3)

        msgs = _tc_messages(result.stdout)
        started = [m for m in msgs if m["_type"] == "testStarted"]
        finished = [m for m in msgs if m["_type"] == "testFinished"]
        assert len(started) == 3, (
            f"Expected 3 testStarted via env var, got {len(started)}\nstdout:\n{result.stdout}"
        )
        assert len(finished) == 3, (
            f"Expected 3 testFinished via env var, got {len(finished)}\nstdout:\n{result.stdout}"
        )

    def test_no_file_progress_line_via_env(self, ftdir):
        """Dumb-mode file progress lines are suppressed via env var activation."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", extra_env=_TC_ENV)
        result.assert_outcomes(passed=5)

        msgs = _tc_messages(result.stdout)
        for test_name in ("test_alpha", "test_beta", "test_param(0)"):
            out = _tc_test_stdout(msgs, test_name)
            assert "[100%]" not in out, (
                f"{test_name}: file progress line leaked via env var activation\n"
                f"stdout:\n{result.stdout}"
            )

    def test_shared_scope_excluded_via_env(self, ftdir):
        """Shared-scope output excluded from testStdOut via env var activation."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", extra_env=_TC_ENV)
        result.assert_outcomes(passed=5)

        msgs = _tc_messages(result.stdout)
        for test_name in ("test_alpha", "test_beta", "test_param(0)", "test_param(1)"):
            out = _tc_test_stdout(msgs, test_name)
            for tag in _SHARED_SETUP_TAGS + _SHARED_TEARDOWN_TAGS:
                assert tag not in out, (
                    f"{test_name}: {tag} leaked into testStdOut via env var\n"
                    f"stdout:\n{result.stdout}"
                )

    def test_captured_output_in_messages_via_env(self, ftdir):
        """Worker print() output appears in testStdOut via env var activation."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "-s", extra_env=_TC_ENV)
        result.assert_outcomes(passed=4)

        msgs = _tc_messages(result.stdout)
        captured = "".join(m.get("out", "") for m in msgs if m["_type"] == "testStdOut")
        for i in range(4):
            assert f"WORKER_OUTPUT_{i}" in captured, (
                f"Missing WORKER_OUTPUT_{i} via env var activation\nstdout:\n{result.stdout}"
            )

    def test_collection_order_via_env(self, ftdir):
        """Parametrized tests reported in collection order via env var activation."""
        ftdir.copy_case("capture_print_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "-s", extra_env=_TC_ENV)
        result.assert_outcomes(passed=4)

        msgs = _tc_messages(result.stdout)
        finished = [m["name"] for m in msgs if m["_type"] == "testFinished"]
        # All parametrized variants should be consecutive (not interleaved with other tests)
        param_names = [n for n in finished if "test_print_worker" in n]
        assert len(param_names) == 4, (
            f"Expected 4 parametrized test results, got {len(param_names)}\n"
            f"stdout:\n{result.stdout}"
        )
        # They should appear as a contiguous block in the finished list
        first_idx = finished.index(param_names[0])
        assert finished[first_idx : first_idx + 4] == param_names, (
            f"Parametrized tests not contiguous in output order\n"
            f"finished: {finished}\nstdout:\n{result.stdout}"
        )
