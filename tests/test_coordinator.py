"""Unit tests for WarmwasserBoostCoordinator logic (no HA instance needed)."""
from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest

from tests.conftest import make_coord, make_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _good_states(ww_temp=45.0, pv_this=2000, pv_next=2000, soc=70):
    """Return a states dict for a successful forecast-start scenario (hour=12)."""
    return {
        "sensor.ww_temp": make_state(ww_temp),
        "sensor.pv_this": make_state(pv_this),
        "sensor.pv_next": make_state(pv_next),
        "sensor.soc": make_state(soc),
        "sun.sun": make_state("above_horizon", {"elevation": 30.0}),
    }


def _at_hour(h, m=0):
    """Return a datetime with given hour/minute for dt_util.now() patching."""
    return datetime.datetime(2024, 6, 15, h, m, 0)


# ---------------------------------------------------------------------------
# _common_preconditions
# ---------------------------------------------------------------------------

class TestCommonPreconditions:
    def test_pass(self):
        coord, _ = make_coord({"sensor.ww_temp": make_state(45.0)})
        assert coord._common_preconditions() is True

    def test_automatik_off(self):
        coord, _ = make_coord({"sensor.ww_temp": make_state(45.0)})
        coord.automatik = False
        assert coord._common_preconditions() is False

    def test_urlaub(self):
        coord, _ = make_coord({"sensor.ww_temp": make_state(45.0)})
        coord.urlaub = True
        assert coord._common_preconditions() is False

    def test_boost_active(self):
        coord, _ = make_coord({"sensor.ww_temp": make_state(45.0)})
        coord.boost_active = True
        assert coord._common_preconditions() is False

    def test_heute_gelaufen(self):
        coord, _ = make_coord({"sensor.ww_temp": make_state(45.0)})
        coord.heute_gelaufen = True
        assert coord._common_preconditions() is False

    def test_ww_above_schwelle(self):
        coord, _ = make_coord({"sensor.ww_temp": make_state(49.0)})
        # start_schwelle default = 48.0; 49 >= 48 → False
        assert coord._common_preconditions() is False

    def test_ww_equal_to_schwelle(self):
        coord, _ = make_coord({"sensor.ww_temp": make_state(48.0)})
        assert coord._common_preconditions() is False

    def test_ww_none(self):
        coord, _ = make_coord({})  # sensor.ww_temp not in states → None
        assert coord._common_preconditions() is False


# ---------------------------------------------------------------------------
# _should_start_forecast
# ---------------------------------------------------------------------------

class TestShouldStartForecast:
    def test_all_good(self):
        coord, _ = make_coord(_good_states())
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is True

    def test_sun_below_horizon(self):
        states = _good_states()
        states["sun.sun"] = make_state("below_horizon", {"elevation": -5.0})
        coord, _ = make_coord(states)
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is False

    def test_elevation_too_low(self):
        states = _good_states()
        states["sun.sun"] = make_state("above_horizon", {"elevation": 10.0})
        coord, _ = make_coord(states)
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is False

    def test_too_early(self):
        coord, _ = make_coord(_good_states())
        # fruhester_start_h default = 11; hour=9 → False
        with patch("homeassistant.util.dt.now", return_value=_at_hour(9)):
            assert coord._should_start_forecast() is False

    def test_pv_this_too_low(self):
        coord, _ = make_coord(_good_states(pv_this=1000))
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is False

    def test_pv_next_too_low(self):
        coord, _ = make_coord(_good_states(pv_next=500))
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is False

    def test_soc_too_low(self):
        coord, _ = make_coord(_good_states(soc=50))
        # min_soc default = 60; 50 <= 60 → False
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is False

    def test_solcast_today_too_low(self):
        states = _good_states()
        states["sensor.solcast_today"] = make_state(3.0)  # < min 6.0
        coord, _ = make_coord(states)
        coord._eid_solcast_today = "sensor.solcast_today"
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is False

    def test_tomorrow_postpone(self):
        """Today marginal but tomorrow much better → postpone."""
        states = _good_states()
        states["sensor.solcast_today"] = make_state(10.0)    # < min_tomorrow(15)
        states["sensor.solcast_tomorrow"] = make_state(20.0)  # > min_tomorrow(15)
        coord, _ = make_coord(states)
        coord._eid_solcast_today = "sensor.solcast_today"
        coord._eid_solcast_tomorrow = "sensor.solcast_tomorrow"
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is False

    def test_no_tomorrow_postpone_when_today_good(self):
        """Today above threshold → no postponement even if tomorrow is also good."""
        states = _good_states()
        states["sensor.solcast_today"] = make_state(20.0)     # >= min_tomorrow(15)
        states["sensor.solcast_tomorrow"] = make_state(25.0)
        coord, _ = make_coord(states)
        coord._eid_solcast_today = "sensor.solcast_today"
        coord._eid_solcast_tomorrow = "sensor.solcast_tomorrow"
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is True

    def test_decay_delay_when_pv_improving(self):
        """WW comfortable until next cycle AND PV improves → delay start."""
        states = _good_states(ww_temp=46.0, pv_this=2000, pv_next=2500)
        coord, _ = make_coord(states)
        # At 09:00 next normal window is at 11:00 → 120 min away
        # WW=46, comfort=42, rate=0.5 → critical=(46-42)/0.5*60=480 min > 150 → ok
        coord._cached_cooling_rate = 0.5
        # pv_next(2500) > pv_this(2000)*1.2=2400 → delay
        with patch("homeassistant.util.dt.now", return_value=_at_hour(9)):
            coord.fruhester_start_h = 9
            assert coord._should_start_forecast() is False

    def test_no_decay_delay_when_pv_not_improving(self):
        """WW comfortable but PV won't improve → start anyway."""
        states = _good_states(ww_temp=46.0, pv_this=2000, pv_next=2100)
        coord, _ = make_coord(states)
        coord._cached_cooling_rate = 0.5
        # pv_next(2100) <= pv_this(2000)*1.2=2400 → no delay
        with patch("homeassistant.util.dt.now", return_value=_at_hour(9)):
            coord.fruhester_start_h = 9
            assert coord._should_start_forecast() is True

    def test_no_decay_delay_without_rate(self):
        """No cached cooling rate → skip decay check, allow start."""
        coord, _ = make_coord(_good_states())
        coord._cached_cooling_rate = None
        with patch("homeassistant.util.dt.now", return_value=_at_hour(12)):
            assert coord._should_start_forecast() is True


# ---------------------------------------------------------------------------
# _should_start_grid_surplus
# ---------------------------------------------------------------------------

class TestShouldStartGridSurplus:
    def _base_states(self, grid=-2000, soc=30):
        return {
            "sensor.ww_temp": make_state(45.0),
            "sensor.grid": make_state(grid),
            "sensor.soc": make_state(soc),
            "sun.sun": make_state("above_horizon", {"elevation": 25.0}),
        }

    def _base_coord(self, **kw):
        coord, _ = make_coord(self._base_states(**kw))
        coord._eid_grid_power = "sensor.grid"
        return coord

    def test_all_good(self):
        assert self._base_coord()._should_start_grid_surplus() is True

    def test_no_grid_sensor(self):
        coord, _ = make_coord(self._base_states())
        # _eid_grid_power stays "" (default from MOCK_CONFIG which has no grid)
        assert coord._should_start_grid_surplus() is False

    def test_sun_below_horizon(self):
        states = self._base_states()
        states["sun.sun"] = make_state("below_horizon", {"elevation": -5.0})
        coord, _ = make_coord(states)
        coord._eid_grid_power = "sensor.grid"
        assert coord._should_start_grid_surplus() is False

    def test_insufficient_surplus(self):
        # grid=-500, threshold=1000 → -500 > -1000 → False
        assert self._base_coord(grid=-500)._should_start_grid_surplus() is False

    def test_soc_too_low(self):
        # soc=15 < min_soc=60 → False
        assert self._base_coord(soc=15)._should_start_grid_surplus() is False

    def test_preconditions_block(self):
        coord = self._base_coord()
        coord.urlaub = True
        assert coord._should_start_grid_surplus() is False


# ---------------------------------------------------------------------------
# _minutes_until_next_normal_cycle
# ---------------------------------------------------------------------------

class TestMinutesUntilNextNormalCycle:
    # Defaults: normal1=05:00-08:00, normal2=11:00-16:00

    def _at(self, h, m=0):
        return _at_hour(h, m)

    def test_in_normal_window1(self):
        coord, _ = make_coord()
        with patch("homeassistant.util.dt.now", return_value=self._at(6, 30)):
            assert coord._minutes_until_next_normal_cycle() == 0

    def test_in_normal_window2(self):
        coord, _ = make_coord()
        with patch("homeassistant.util.dt.now", return_value=self._at(13)):
            assert coord._minutes_until_next_normal_cycle() == 0

    def test_before_window1(self):
        # 04:00 → next start is 05:00 → 60 min
        coord, _ = make_coord()
        with patch("homeassistant.util.dt.now", return_value=self._at(4)):
            assert coord._minutes_until_next_normal_cycle() == 60

    def test_between_windows(self):
        # 09:00 → next start is 11:00 → 120 min
        coord, _ = make_coord()
        with patch("homeassistant.util.dt.now", return_value=self._at(9)):
            assert coord._minutes_until_next_normal_cycle() == 120

    def test_after_all_windows(self):
        # 20:00 → next is 05:00 next day → (24-20)*60 + 5*60 = 240+300 = 540 min
        coord, _ = make_coord()
        with patch("homeassistant.util.dt.now", return_value=self._at(20)):
            assert coord._minutes_until_next_normal_cycle() == 540


# ---------------------------------------------------------------------------
# _ww_ok_until_next_normal_cycle
# ---------------------------------------------------------------------------

class TestWwOkUntilNextNormalCycle:
    # All tests fix time at 09:00 → minutes_until_normal = 120

    def _coord_at9(self, ww_temp, rate):
        states = {"sensor.ww_temp": make_state(ww_temp)}
        coord, _ = make_coord(states)
        coord._cached_cooling_rate = rate
        return coord

    def test_no_rate(self):
        coord = self._coord_at9(47.0, None)
        with patch("homeassistant.util.dt.now", return_value=_at_hour(9)):
            assert coord._ww_ok_until_next_normal_cycle() is False

    def test_rate_zero(self):
        coord = self._coord_at9(47.0, 0.0)
        with patch("homeassistant.util.dt.now", return_value=_at_hour(9)):
            assert coord._ww_ok_until_next_normal_cycle() is False

    def test_ww_comfortable(self):
        # ww=47, comfort=42, rate=0.5 → critical=600 min; normal+margin=150 → 600>150 → True
        coord = self._coord_at9(47.0, 0.5)
        with patch("homeassistant.util.dt.now", return_value=_at_hour(9)):
            assert coord._ww_ok_until_next_normal_cycle() is True

    def test_ww_not_comfortable(self):
        # ww=43, comfort=42, rate=2.0 → critical=30 min; normal+margin=150 → 30<150 → False
        coord = self._coord_at9(43.0, 2.0)
        with patch("homeassistant.util.dt.now", return_value=_at_hour(9)):
            assert coord._ww_ok_until_next_normal_cycle() is False

    def test_ww_temp_none(self):
        coord, _ = make_coord({})  # no ww_temp state → _float returns None
        coord._cached_cooling_rate = 0.5
        with patch("homeassistant.util.dt.now", return_value=_at_hour(9)):
            assert coord._ww_ok_until_next_normal_cycle() is False
