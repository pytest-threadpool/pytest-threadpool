"""Tests for standard and custom pytest marker compatibility under parallel execution."""

CUSTOM_MARKER_INI = (
    "[pytest]\nmarkers =\n    smoke: smoke tests\n    regression: regression tests\n"
)


class TestStandardMarks:
    """Verify built-in pytest markers work correctly with --threadpool."""

    def test_skip_skipif_xfail_parametrize(self, ftdir):
        """skip, skipif, xfail, and parametrize all work in a parallel class."""
        ftdir.copy_case("marks_standard")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=4, skipped=2, xfailed=1)

    def test_keyword_selection(self, ftdir):
        """pytest -k filtering works with --threadpool."""
        ftdir.copy_case("marks_standard")
        result = ftdir.run_pytest("--threadpool", "auto", "-k", "param or plain")
        result.assert_outcomes(passed=4)

    def test_marker_selection(self, ftdir):
        """pytest -m filtering works with --threadpool."""
        ftdir.copy_case("marks_standard")
        result = ftdir.run_pytest("--threadpool", "auto", "-m", "skip")
        result.assert_outcomes(skipped=1)


class TestCustomMarks:
    """Verify user-defined custom markers work with --threadpool."""

    def _setup_custom(self, ftdir):
        ftdir.copy_case("marks_custom")
        ftdir.path.joinpath("pytest.ini").write_text(CUSTOM_MARKER_INI)

    def test_select_single_custom_marker(self, ftdir):
        """'-m smoke' selects only smoke-marked tests."""
        self._setup_custom(ftdir)
        result = ftdir.run_pytest("--threadpool", "auto", "-m", "smoke")
        result.assert_outcomes(passed=2)

    def test_select_marker_and_expression(self, ftdir):
        """'-m \"smoke and regression\"' selects only doubly-marked test."""
        self._setup_custom(ftdir)
        result = ftdir.run_pytest(
            "--threadpool",
            "auto",
            "-m",
            "smoke and regression",
        )
        result.assert_outcomes(passed=1)

    def test_select_marker_or_expression(self, ftdir):
        """'-m \"smoke or regression\"' selects all marked tests."""
        self._setup_custom(ftdir)
        result = ftdir.run_pytest(
            "--threadpool",
            "auto",
            "-m",
            "smoke or regression",
        )
        result.assert_outcomes(passed=3)

    def test_select_marker_not_expression(self, ftdir):
        """'-m \"not smoke\"' excludes smoke tests."""
        self._setup_custom(ftdir)
        result = ftdir.run_pytest(
            "--threadpool",
            "auto",
            "-m",
            "not smoke",
        )
        result.assert_outcomes(passed=2)
