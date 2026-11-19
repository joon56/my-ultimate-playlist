"""실험 3: 다리 진자 주기 검출 (SPEC §5.8, D-24·D-41·D-58·D-73). 합성 자이로 신호에서 정답을 되찾는다."""

import numpy as np
import pytest

from walkmusic import exp3
from walkmusic.synthetic import SwingSpec, make_swing_gyro


@pytest.mark.parametrize("period", [1.55, 1.37])
def test_swing_period_recovered(params, period):
    t, gyro, _ = make_swing_gyro(SwingSpec(period_s=period, seed=1))
    r = exp3.analyze_gyro(t, gyro, params)
    assert r["swing_period_s"] == pytest.approx(period, rel=0.005)
    assert r["n_cycles"] >= 8
    assert "few_cycles" not in r["flags"]


def test_swing_amplitude_and_peak_speed(params):
    t, gyro, truth = make_swing_gyro(SwingSpec(period_s=1.531, omega_amp_rad_s=2.125, decay_per_s=0.0, seed=2))
    r = exp3.analyze_gyro(t, gyro, params)
    assert r["omega_peak_rad_s"] == pytest.approx(2.125, rel=0.03)
    assert r["amp_deg"] == pytest.approx(truth["amp_deg"], rel=0.03)


def test_short_swing_is_flagged(params):
    t, gyro, _ = make_swing_gyro(SwingSpec(swing_s=9.0, seed=3))
    assert "few_cycles" in exp3.analyze_gyro(t, gyro, params)["flags"]


def test_still_recording_has_no_swing(params):
    rng = np.random.default_rng(0)
    t = np.arange(0, 20, 0.01)
    r = exp3.analyze_gyro(t, 0.02 * rng.standard_normal((len(t), 3)), params)
    assert np.isnan(r["swing_period_s"])
    assert "no_swing" in r["flags"]
