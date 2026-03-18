"""Hook specifications for pytest-threadpool.

Implement these hooks in a conftest.py or plugin to customize
parallel test reporting.
"""


def pytest_threadpool_report(item, report, captured_out, captured_err):
    """Called after a parallel test is reported.

    Receives the test item, its report, and any captured worker
    stdout/stderr.  Return ``True`` to suppress the default
    output handling (captured-output sections will not be added
    to the report).  Return ``None`` to let the default proceed.

    Parameters
    ----------
    item : pytest.Item
        The test item that was executed.
    report : pytest.TestReport
        The call-phase report (or setup report on setup failure).
    captured_out : str
        Stdout captured from the worker thread during this test.
    captured_err : str
        Stderr captured from the worker thread during this test.
    """
