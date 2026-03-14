"""Tests for xunit-style setup/teardown under parallel execution."""

import pytest


class TestXunitUnderParallel:
    """Verify xunit setup/teardown hooks work correctly with parallel children."""

    def test_class_setup_teardown(self, ftdir):
        """setup_class runs once before parallel methods."""
        ftdir.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestClassSetup:
                log = []

                @classmethod
                def setup_class(cls):
                    cls.log.append("setup_class")

                @classmethod
                def teardown_class(cls):
                    cls.log.append("teardown_class")

                def test_a(self):
                    assert "setup_class" in self.log

                def test_b(self):
                    count = self.log.count("setup_class")
                    assert count == 1

            def test_verify():
                assert TestClassSetup.log[0] == "setup_class"
        """)
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_method_setup_teardown(self, ftdir):
        """setup_method runs per method even with parallel children."""
        ftdir.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestMethodSetup:
                log = []

                def setup_method(self, method):
                    self.log.append(f"setup_{method.__name__}")

                def test_a(self):
                    assert "setup_test_a" in self.log

                def test_b(self):
                    assert "setup_test_b" in self.log

                def test_c(self):
                    assert "setup_test_c" in self.log

            def test_verify():
                setups = [x for x in TestMethodSetup.log if x.startswith("setup_")]
                assert len(setups) >= 3
        """)
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_combined_class_and_method(self, ftdir):
        """Both setup_class and setup_method work together."""
        ftdir.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestCombined:
                log = []

                @classmethod
                def setup_class(cls):
                    cls.log.append("class_setup")

                def setup_method(self, method):
                    self.log.append(f"method_setup_{method.__name__}")

                def test_x(self):
                    pass

                def test_y(self):
                    pass

            def test_verify():
                assert TestCombined.log[0] == "class_setup"
                method_setups = [x for x in TestCombined.log
                                 if x.startswith("method_setup_")]
                assert len(method_setups) >= 2
        """)
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_module_setup_teardown(self, ftdir):
        """Module-level setup_module / teardown_module work."""
        ftdir.makepyfile("""
            class _State:
                log = []

            def setup_module(module):
                _State.log.append("setup_module")

            def teardown_module(module):
                _State.log.append("teardown_module")

            def test_setup_ran():
                assert "setup_module" in _State.log
        """)
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=1)

    def test_function_setup_teardown(self, ftdir):
        """Function-level setup_function / teardown_function work."""
        ftdir.makepyfile("""
            class _State:
                log = []

            def setup_function(function):
                _State.log.append(f"setup_{function.__name__}")

            def teardown_function(function):
                _State.log.append(f"teardown_{function.__name__}")

            def test_alpha():
                assert "setup_test_alpha" in _State.log

            def test_beta():
                assert "setup_test_beta" in _State.log

            def test_verify():
                assert "teardown_test_alpha" in _State.log
        """)
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)
