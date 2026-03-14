"""Many slow parallel tests — SIGINT must still produce output."""
import time
from pathlib import Path

import pytest

_READY = Path(__file__).parent / ".sigint_ready"


@pytest.mark.parallelizable("children")
class TestManySlowParallel:
    def test_slow_00(self):
        _READY.write_text("ready")
        time.sleep(30)
    def test_slow_01(self): time.sleep(30)
    def test_slow_02(self): time.sleep(30)
    def test_slow_03(self): time.sleep(30)
    def test_slow_04(self): time.sleep(30)
    def test_slow_05(self): time.sleep(30)
    def test_slow_06(self): time.sleep(30)
    def test_slow_07(self): time.sleep(30)
    def test_slow_08(self): time.sleep(30)
    def test_slow_09(self): time.sleep(30)
    def test_slow_10(self): time.sleep(30)
    def test_slow_11(self): time.sleep(30)
    def test_slow_12(self): time.sleep(30)
    def test_slow_13(self): time.sleep(30)
    def test_slow_14(self): time.sleep(30)
    def test_slow_15(self): time.sleep(30)
    def test_slow_16(self): time.sleep(30)
    def test_slow_17(self): time.sleep(30)
    def test_slow_18(self): time.sleep(30)
    def test_slow_19(self): time.sleep(30)
