"""Tests for correct scoping of captured output across fixture levels.

Verifies that setup/teardown output from each fixture scope (session,
package, module, class, function) is associated with the correct scope
in passive (``-vs``) and dumb (``-v``) terminal modes.

For TeamCity/IDE output scoping, see ``test_ide_reporter.py``.

Hierarchy (inner to outer):
  test:    FUNCTION_SETUP, CALL_xxx, FUNCTION_TEARDOWN
  class:   CLASS_SETUP, <tests>, CLASS_TEARDOWN
  module:  MODULE_SETUP, <class>, MODULE_TEARDOWN
  package: PACKAGE_SETUP, <module>, PACKAGE_TEARDOWN
  session: SESSION_SETUP, <package>, SESSION_TEARDOWN
"""

import re

_SHARED_SETUP_TAGS = ("SESSION_SETUP", "PACKAGE_SETUP", "MODULE_SETUP", "CLASS_SETUP")
_SHARED_TEARDOWN_TAGS = (
    "CLASS_TEARDOWN",
    "MODULE_TEARDOWN",
    "PACKAGE_TEARDOWN",
    "SESSION_TEARDOWN",
)
_ALL_TAGS = (
    "SESSION_SETUP",
    "SESSION_TEARDOWN",
    "PACKAGE_SETUP",
    "PACKAGE_TEARDOWN",
    "MODULE_SETUP",
    "MODULE_TEARDOWN",
    "CLASS_SETUP",
    "CLASS_TEARDOWN",
    "FUNCTION_SETUP",
    "FUNCTION_TEARDOWN",
    "CALL_ALPHA",
    "CALL_BETA",
    "CALL_PARAM_0",
    "CALL_PARAM_1",
    "CALL_PARAM_2",
)


def _parse_passive_blocks(stdout: str) -> dict[str, list[str]]:
    """Parse ``-vs`` output into per-test output blocks.

    Returns a dict mapping test short names (e.g. ``test_alpha``,
    ``test_param[0]``) to the list of output lines that appear after
    that test's PASSED/FAILED line and before the next test, summary,
    or shared-scope teardown marker.
    """
    blocks: dict[str, list[str]] = {}
    current_test = None
    current_lines: list[str] = []

    for line in stdout.splitlines():
        # Match re-emitted result lines: "...::test_name PASSED" or "...::test_name[0] PASSED"
        m = re.search(r"::(\w+(?:\[\d+\])?)\s+(?:\033\[\d+[;]?\d*m)?(?:PASSED|FAILED)", line)
        if m:
            if current_test is not None:
                blocks[current_test] = current_lines
            current_test = m.group(1)
            current_lines = []
            continue

        if line.strip().startswith("=") and ("passed" in line or "failed" in line):
            if current_test is not None:
                blocks[current_test] = current_lines
            break

        # Shared-scope teardown tags end the current test's block.
        stripped = line.strip()
        if stripped in _SHARED_TEARDOWN_TAGS:
            if current_test is not None:
                blocks[current_test] = current_lines
                current_test = None
                current_lines = []
            continue

        if current_test is not None and stripped:
            current_lines.append(stripped)

    return blocks


# ---------------------------------------------------------------------------
# Per-test output (passive mode, function scope only)
# ---------------------------------------------------------------------------


class TestPerTestOutput:
    """Each test's output contains only its own function-level setup, call, and teardown."""

    def test_passive_test_has_only_function_output(self, ftdir):
        """In -vs mode, each test block contains only function-scoped output."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        blocks = _parse_passive_blocks(result.stdout)
        for test_name, call_tag in (
            ("test_alpha", "CALL_ALPHA"),
            ("test_beta", "CALL_BETA"),
            ("test_param[0]", "CALL_PARAM_0"),
            ("test_param[1]", "CALL_PARAM_1"),
            ("test_param[2]", "CALL_PARAM_2"),
        ):
            block_text = "\n".join(blocks.get(test_name, []))
            assert "FUNCTION_SETUP" in block_text, (
                f"{test_name}: missing FUNCTION_SETUP\nblock: {blocks.get(test_name)}\n"
                f"stdout:\n{result.stdout}"
            )
            assert call_tag in block_text, (
                f"{test_name}: missing {call_tag}\nblock: {blocks.get(test_name)}\n"
                f"stdout:\n{result.stdout}"
            )
            assert "FUNCTION_TEARDOWN" in block_text, (
                f"{test_name}: missing FUNCTION_TEARDOWN\nblock: {blocks.get(test_name)}\n"
                f"stdout:\n{result.stdout}"
            )

    def test_passive_test_excludes_shared_scope(self, ftdir):
        """In -vs mode, shared-scope setup/teardown does not appear in test blocks."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        blocks = _parse_passive_blocks(result.stdout)
        for test_name in ("test_alpha", "test_beta", "test_param[0]", "test_param[1]"):
            block_text = "\n".join(blocks.get(test_name, []))
            for tag in _SHARED_SETUP_TAGS + _SHARED_TEARDOWN_TAGS:
                assert tag not in block_text, (
                    f"{test_name}: {tag} leaked into test block\n"
                    f"block: {blocks.get(test_name)}\nstdout:\n{result.stdout}"
                )


# ---------------------------------------------------------------------------
# Dumb mode (default capture, no TTY)
# ---------------------------------------------------------------------------


class TestDumbModeClean:
    """In dumb mode (-v without -s), no setup/call/teardown output leaks into stdout."""

    def test_no_setup_output_in_dumb_mode(self, ftdir):
        """Default capture suppresses all fixture/call print output."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-v")
        result.assert_outcomes(passed=5)

        for tag in _ALL_TAGS:
            assert tag not in result.stdout, (
                f"{tag} leaked into dumb-mode output\nstdout:\n{result.stdout}"
            )

    def test_no_passed_reemit_in_dumb_mode(self, ftdir):
        """PASSED re-emit lines do not appear in dumb mode (file line suffices)."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-v")
        result.assert_outcomes(passed=5)

        reemit_lines = [
            ln for ln in result.outlines if "PASSED" in ln and "::" in ln and "[" not in ln
        ]
        assert not reemit_lines, (
            f"PASSED re-emit lines found in dumb mode: {reemit_lines}\nstdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Scope ordering (passive mode)
# ---------------------------------------------------------------------------


class TestClassScopeOutput:
    """Class-level output: CLASS_SETUP, all tests with their output, CLASS_TEARDOWN."""

    def test_passive_class_setup_before_first_test(self, ftdir):
        """In -vs mode, CLASS_SETUP appears before the first test."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        lines = result.stdout.splitlines()
        class_setup_idx = next((i for i, ln in enumerate(lines) if "CLASS_SETUP" in ln), None)
        first_passed_idx = next((i for i, ln in enumerate(lines) if "PASSED" in ln), None)
        assert class_setup_idx is not None, f"CLASS_SETUP not found\nstdout:\n{result.stdout}"
        assert first_passed_idx is not None
        assert class_setup_idx < first_passed_idx, (
            f"CLASS_SETUP (line {class_setup_idx}) should appear before "
            f"first PASSED (line {first_passed_idx})\nstdout:\n{result.stdout}"
        )

    def test_passive_class_teardown_after_last_test(self, ftdir):
        """In -vs mode, CLASS_TEARDOWN appears after the last test."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        lines = result.stdout.splitlines()
        class_td_idx = next((i for i, ln in enumerate(lines) if "CLASS_TEARDOWN" in ln), None)
        last_passed_idx = max((i for i, ln in enumerate(lines) if "PASSED" in ln), default=None)
        assert class_td_idx is not None, f"CLASS_TEARDOWN not found\nstdout:\n{result.stdout}"
        assert last_passed_idx is not None
        assert class_td_idx > last_passed_idx, (
            f"CLASS_TEARDOWN (line {class_td_idx}) should appear after "
            f"last PASSED (line {last_passed_idx})\nstdout:\n{result.stdout}"
        )


class TestModuleScopeOutput:
    """Module-level output wraps class-level output."""

    def test_passive_module_setup_before_class_setup(self, ftdir):
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        lines = result.stdout.splitlines()
        mod_idx = next((i for i, ln in enumerate(lines) if "MODULE_SETUP" in ln), None)
        cls_idx = next((i for i, ln in enumerate(lines) if "CLASS_SETUP" in ln), None)
        assert mod_idx is not None, f"MODULE_SETUP not found\nstdout:\n{result.stdout}"
        assert cls_idx is not None
        assert mod_idx < cls_idx, (
            f"MODULE_SETUP should precede CLASS_SETUP\nstdout:\n{result.stdout}"
        )

    def test_passive_module_teardown_after_class_teardown(self, ftdir):
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        lines = result.stdout.splitlines()
        mod_td = next((i for i, ln in enumerate(lines) if "MODULE_TEARDOWN" in ln), None)
        cls_td = next((i for i, ln in enumerate(lines) if "CLASS_TEARDOWN" in ln), None)
        assert mod_td is not None, f"MODULE_TEARDOWN not found\nstdout:\n{result.stdout}"
        assert cls_td is not None
        assert mod_td > cls_td, (
            f"MODULE_TEARDOWN should follow CLASS_TEARDOWN\nstdout:\n{result.stdout}"
        )


class TestPackageScopeOutput:
    """Package-level output wraps module-level output."""

    def test_passive_package_setup_before_module_setup(self, ftdir):
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        lines = result.stdout.splitlines()
        pkg_idx = next((i for i, ln in enumerate(lines) if "PACKAGE_SETUP" in ln), None)
        mod_idx = next((i for i, ln in enumerate(lines) if "MODULE_SETUP" in ln), None)
        assert pkg_idx is not None, f"PACKAGE_SETUP not found\nstdout:\n{result.stdout}"
        assert mod_idx is not None
        assert pkg_idx < mod_idx

    def test_passive_package_teardown_after_module_teardown(self, ftdir):
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        lines = result.stdout.splitlines()
        pkg_td = next((i for i, ln in enumerate(lines) if "PACKAGE_TEARDOWN" in ln), None)
        mod_td = next((i for i, ln in enumerate(lines) if "MODULE_TEARDOWN" in ln), None)
        assert pkg_td is not None, f"PACKAGE_TEARDOWN not found\nstdout:\n{result.stdout}"
        assert mod_td is not None
        assert pkg_td > mod_td


class TestSessionScopeOutput:
    """Session-level output wraps everything."""

    def test_passive_session_setup_before_package_setup(self, ftdir):
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        lines = result.stdout.splitlines()
        ses_idx = next((i for i, ln in enumerate(lines) if "SESSION_SETUP" in ln), None)
        pkg_idx = next((i for i, ln in enumerate(lines) if "PACKAGE_SETUP" in ln), None)
        assert ses_idx is not None, f"SESSION_SETUP not found\nstdout:\n{result.stdout}"
        assert pkg_idx is not None
        assert ses_idx < pkg_idx

    def test_passive_session_teardown_after_package_teardown(self, ftdir):
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        lines = result.stdout.splitlines()
        ses_td = next((i for i, ln in enumerate(lines) if "SESSION_TEARDOWN" in ln), None)
        pkg_td = next((i for i, ln in enumerate(lines) if "PACKAGE_TEARDOWN" in ln), None)
        assert ses_td is not None, f"SESSION_TEARDOWN not found\nstdout:\n{result.stdout}"
        assert pkg_td is not None
        assert ses_td > pkg_td

    def test_passive_all_output_present(self, ftdir):
        """In -vs mode, all scope outputs appear somewhere in stdout."""
        ftdir.copy_case("capture_scoped_output")
        result = ftdir.run_pytest("--threadpool", "3", "-vs")
        result.assert_outcomes(passed=5)

        for tag in _ALL_TAGS:
            assert tag in result.stdout, f"{tag} missing from output\nstdout:\n{result.stdout}"
