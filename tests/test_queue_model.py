"""
tests/test_queue_model.py — Sanity checks for M/M/c analytical model.

Run: pytest tests/ -v
"""

import pytest
import sys
sys.path.insert(0, str(__file__).replace("/tests/test_queue_model.py", ""))

from sim.queue_model import mmc_metrics, erlang_c, scan_staffing_levels


class TestErlangC:
    def test_single_server_full_load(self):
        """rho → 1 should push P(wait) → 1."""
        c = erlang_c(1, 0.999)
        assert c > 0.99

    def test_many_servers_low_load(self):
        """Many servers, low load → almost nobody waits."""
        c = erlang_c(10, 0.1)
        assert c < 0.01

    def test_unstable_returns_one(self):
        """rho >= 1 → P(wait) = 1."""
        assert erlang_c(1, 1.0) == 1.0
        assert erlang_c(2, 1.5) == 1.0


class TestMMCMetrics:
    def test_stable_basic(self):
        """M/M/1, lam=1, mu=2 → rho=0.5, Wq=0.5hr=30min."""
        m = mmc_metrics(lam=1, mu=2, c=1)
        assert m["stable"] is True
        assert abs(m["rho"] - 0.5) < 1e-6
        # Wq = rho/(mu*(1-rho)) * 60 = 0.5/(2*0.5)*60 = 30 min
        assert abs(m["Wq"] - 30.0) < 0.5

    def test_unstable_detection(self):
        """lam > c*mu should be unstable."""
        m = mmc_metrics(lam=10, mu=2, c=3)  # rho = 10/6 > 1
        assert m["stable"] is False

    def test_more_servers_reduces_wait(self):
        """Adding servers should reduce Wq monotonically."""
        waits = [mmc_metrics(20, 8, c)["Wq"] for c in range(3, 8)
                 if mmc_metrics(20, 8, c)["stable"]]
        assert waits == sorted(waits, reverse=True)

    def test_littles_law(self):
        """Verify L = lambda * W (Little's Law)."""
        m = mmc_metrics(lam=10, mu=5, c=3)
        assert m["stable"]
        # L = lam * W; W is in minutes so convert lam to per-minute
        lam_per_min = 10 / 60
        expected_L = lam_per_min * m["W"]
        assert abs(m["L"] - expected_L) < 0.05


class TestScanStaffing:
    def test_returns_correct_range(self):
        results = scan_staffing_levels(10, 4, c_min=1, c_max=5)
        assert len(results) == 5
        assert [r["c"] for r in results] == [1, 2, 3, 4, 5]

    def test_first_few_unstable(self):
        """lam=20, mu=5 → need c>=4 for stability."""
        results = scan_staffing_levels(20, 5, c_min=1, c_max=6)
        stabilities = [r["stable"] for r in results]
        # c=1,2,3 unstable; c=4,5,6 stable
        assert stabilities[:3] == [False, False, False]
        assert all(stabilities[3:])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
