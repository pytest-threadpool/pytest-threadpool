"""Pytester tests for parallel scope types and marker priority."""


class TestParallelScopes:
    """Verify parameters, all, children scopes and override priority."""

    def test_parameters_scope(self, pytester):
        """Parametrized variants run concurrently with 'parameters' scope."""
        pytester.makepyfile("""
            import threading
            import pytest

            @pytest.mark.parallelizable("parameters")
            @pytest.mark.parametrize("v", ["x", "y", "z"])
            def test_param(v):
                barrier = test_param._barrier
                barrier.wait()

            test_param._barrier = threading.Barrier(3, timeout=10)
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_all_scope_merges_children_and_params(self, pytester):
        """'all' merges plain methods and parametrized variants into one batch."""
        pytester.makepyfile("""
            import threading
            import pytest

            @pytest.mark.parallelizable("all")
            class TestAll:
                barrier = threading.Barrier(5, timeout=10)

                @pytest.mark.parametrize("n", [1, 2, 3])
                def test_param(self, n):
                    self.barrier.wait()

                def test_plain_a(self):
                    self.barrier.wait()

                def test_plain_b(self):
                    self.barrier.wait()
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "5")
        result.assert_outcomes(passed=5)

    def test_children_does_not_merge_params(self, pytester):
        """'children' keeps parametrized variants in separate groups."""
        pytester.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestChildren:
                results = {}

                @pytest.mark.parametrize("val", ["a", "b"])
                def test_item(self, val):
                    self.results[val] = True

            def test_verify():
                assert set(TestChildren.results.keys()) == {"a", "b"}
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_own_marker_overrides_class(self, pytester):
        """Method's own 'parameters' overrides class 'children'."""
        pytester.makepyfile("""
            import threading
            import pytest

            @pytest.mark.parallelizable("children")
            class TestOverride:
                child_barrier = threading.Barrier(2, timeout=10)

                def test_child_a(self):
                    self.child_barrier.wait()

                def test_child_b(self):
                    self.child_barrier.wait()

                @pytest.mark.parallelizable("parameters")
                @pytest.mark.parametrize("v", [1, 2, 3])
                def test_own_param(self, v):
                    pass

            def test_verify():
                # If own param joined children batch, barrier(2) would deadlock
                assert True
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "5")
        result.assert_outcomes(passed=6)

    def test_not_parallelizable_overrides_class(self, pytester):
        """@not_parallelizable on a method opts it out of class children batch."""
        pytester.makepyfile("""
            import time
            import pytest

            @pytest.mark.parallelizable("children")
            class TestMixed:
                log = []

                def test_parallel_a(self):
                    time.sleep(0.05)
                    self.log.append("a")

                @pytest.mark.not_parallelizable
                def test_seq_b(self):
                    self.log.append("b")

                def test_parallel_c(self):
                    self.log.append("c")

            def test_verify():
                assert "a" in TestMixed.log
                assert "b" in TestMixed.log
                assert "c" in TestMixed.log
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_not_parallelizable_bare_function(self, pytester):
        """@not_parallelizable on bare functions in a parallel module."""
        pytester.makepyfile("""
            import time
            import pytest

            pytestmark = pytest.mark.parallelizable("children")

            @pytest.mark.not_parallelizable
            def test_seq_a():
                time.sleep(0.05)
                print("ORDER:a")

            @pytest.mark.not_parallelizable
            def test_seq_b():
                print("ORDER:b")
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto", "-s")
        result.assert_outcomes(passed=2)
        order = [l.split("ORDER:")[1] for l in result.outlines if "ORDER:" in l]
        assert order == ["a", "b"]

    def test_module_level_children(self, pytester):
        """Module-level pytestmark parallelizable('children') works."""
        pytester.makepyfile("""
            import threading
            import pytest

            pytestmark = pytest.mark.parallelizable("children")

            class _State:
                barrier = threading.Barrier(3, timeout=10)

            def test_a():
                _State.barrier.wait()

            def test_b():
                _State.barrier.wait()

            def test_c():
                _State.barrier.wait()
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "3")
        result.assert_outcomes(passed=3)
