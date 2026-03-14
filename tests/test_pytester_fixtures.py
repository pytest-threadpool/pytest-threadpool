"""Pytester tests for fixture correctness under parallel execution."""


class TestFixturesUnderParallel:
    """Verify fixture setup/teardown behaves correctly with parallel children."""

    def test_class_scoped_fixture_setup_once(self, pytester):
        """Class-scoped fixture runs exactly once despite parallel methods."""
        pytester.makepyfile("""
            import threading
            import pytest

            @pytest.mark.parallelizable("children")
            class TestOnce:
                setup_count = []
                barrier = threading.Barrier(3, timeout=10)

                @pytest.fixture(autouse=True, scope="class")
                def db(self):
                    self.setup_count.append(1)
                    yield

                def test_a(self):
                    self.barrier.wait()
                    assert len(self.setup_count) == 1

                def test_b(self):
                    self.barrier.wait()
                    assert len(self.setup_count) == 1

                def test_c(self):
                    self.barrier.wait()
                    assert len(self.setup_count) == 1
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_class_scoped_yield_fixture(self, pytester):
        """Class-scoped yield fixture: setup before parallel, teardown after."""
        pytester.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestYield:
                log = []

                @pytest.fixture(autouse=True, scope="class")
                def db(self):
                    self.log.append("setup")
                    yield "conn"
                    self.log.append("teardown")

                def test_a(self):
                    assert "setup" in self.log

                def test_b(self):
                    assert "setup" in self.log

            def test_verify():
                assert "setup" in TestYield.log
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_function_scoped_fixture(self, pytester):
        """Function-scoped fixtures get fresh values per test."""
        pytester.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestFuncScope:
                call_log = []

                @pytest.fixture(autouse=True)
                def counter(self):
                    idx = len(self.call_log)
                    self.call_log.append(f"setup_{idx}")
                    yield idx

                def test_a(self, counter):
                    assert isinstance(counter, int)

                def test_b(self, counter):
                    assert isinstance(counter, int)

                def test_c(self, counter):
                    assert isinstance(counter, int)

            def test_verify():
                setups = [x for x in TestFuncScope.call_log if x.startswith("setup_")]
                assert len(setups) == 3
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_parameterized_fixture(self, pytester):
        """Parameterized class-scoped fixture expands correctly."""
        pytester.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestParamFixture:
                @pytest.fixture(params=["alpha", "beta"], scope="class", autouse=True)
                def variant(self, request):
                    return request.param

                def test_is_str(self, variant):
                    assert isinstance(variant, str)

                def test_in_set(self, variant):
                    assert variant in {"alpha", "beta"}
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_multiple_fixture_scopes(self, pytester):
        """Session + module + class fixtures compose correctly."""
        pytester.makepyfile("""
            import pytest

            @pytest.fixture(scope="session")
            def session_res():
                return {"from": "session"}

            @pytest.fixture(scope="module")
            def module_res():
                return {"from": "module"}

            @pytest.mark.parallelizable("children")
            class TestCompose:
                def test_session(self, session_res):
                    assert session_res["from"] == "session"

                def test_module(self, module_res):
                    assert module_res["from"] == "module"

                def test_both(self, session_res, module_res):
                    assert session_res and module_res
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_yield_fixture_cleanup(self, pytester):
        """Yield fixture teardown runs after all parallel methods."""
        pytester.makepyfile("""
            import pytest

            @pytest.mark.parallelizable("children")
            class TestCleanup:
                flag = {"cleaned": False}

                @pytest.fixture(autouse=True, scope="class")
                def resource(self):
                    self.flag["cleaned"] = False
                    yield
                    self.flag["cleaned"] = True

                def test_a(self):
                    assert not self.flag["cleaned"]

                def test_b(self):
                    assert not self.flag["cleaned"]

            def test_verify():
                assert TestCleanup.flag["cleaned"]
        """)
        result = pytester.runpytest_subprocess("--freethreaded", "auto")
        result.assert_outcomes(passed=3)
