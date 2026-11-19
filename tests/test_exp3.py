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


@pytest.mark.parametrize("seed", range(5))
def test_cycle_count_not_short_after_axis_refinement(params, seed):
    # 주기 1.8 s로 20 s 흔들면 봉우리 사이가 10개다. 축을 다시 구할 때 부호가 뒤집혀 하나 모자라게 세면 안 된다
    # (검토 #6, 10주기 미만이면 '다시 하기'가 뜬다). 합성 신호는 흔들기를 뚝 끊어 끝에 봉우리가 하나 더 생길 수 있다.
    t, gyro, _ = make_swing_gyro(SwingSpec(period_s=1.8, swing_s=20.0, seed=seed))
    r = exp3.analyze_gyro(t, gyro, params)
    assert r["n_cycles_total"] >= 10
    assert "few_cycles" not in r["flags"]
    assert r["swing_period_s"] == pytest.approx(1.8, rel=0.005)


def test_walking_before_swing_is_not_taken_as_swing(params):
    # 정강이 폰으로 계단까지 걸어간 뒤 흔들면, 걷기의 보폭 리듬(약 1.1 s)을 진자로 잡지 않는다(검토 #8)
    t, gyro, _ = make_swing_gyro(SwingSpec(period_s=1.55, seed=3))
    fs = 1 / np.median(np.diff(t))
    rng = np.random.default_rng(1)
    tw = np.arange(0, 16 * 1.1, 1 / fs)
    ph = (tw % 1.1) / 1.1
    w = np.where(ph < 0.4, 5.0 * np.sin(np.pi * ph / 0.4) ** 2, -1.2 * np.sin(np.pi * (ph - 0.4) / 0.6))
    axis = np.array([0.25, 0.92, 0.30]) / np.linalg.norm([0.25, 0.92, 0.30])
    tt = np.concatenate([tw, tw[-1] + 1 / fs + (t - t[0])])
    gg = np.vstack([np.outer(w, axis) + 0.05 * rng.standard_normal((len(tw), 3)), gyro])
    acc = np.ones(len(tt))  # 걷는 동안 발이 닿을 때마다 정강이 가속도가 크게 튄다
    for s in np.arange(0.45, tw[-1], 1.1):
        acc[(tt >= s) & (tt < s + 0.03)] = 4.0
    r = exp3.analyze_gyro(tt, gg, params, acc_t=tt, acc_mag_g=acc)
    assert r["swing_period_s"] == pytest.approx(1.55, rel=0.01)


def test_short_recording_does_not_crash(params):
    t = np.arange(0, 2.0, 0.01)  # 실수로 2초만 기록(검토 #9)
    r = exp3.analyze_gyro(t, 0.5 * np.random.default_rng(0).standard_normal((len(t), 3)), params)
    assert "no_swing" in r["flags"]


@pytest.mark.parametrize("seed", range(5))
def test_cycle_count_takes_direction_with_more_cycles(params, seed):
    # 19 s × 주기 1.8 s = 10.6주기. 한쪽 봉우리로 세면 끝 위상에 따라 9 또는 10이 되므로 많은 쪽을 쓴다
    t, gyro, _ = make_swing_gyro(SwingSpec(period_s=1.8, swing_s=19.0, seed=seed))
    r = exp3.analyze_gyro(t, gyro, params)
    assert r["n_cycles_total"] == 10
    assert "few_cycles" not in r["flags"]


def test_other_rhythm_flagged_without_accelerometer(params):
    # 가속도 없이 걷기 + 흔들기가 한 기록에 있으면 어느 쪽을 골랐든 사람이 보게 표시한다
    t, gyro, _ = make_swing_gyro(SwingSpec(period_s=1.55, seed=3))
    fs = 1 / np.median(np.diff(t))
    tw = np.arange(0, 16 * 1.1, 1 / fs)
    ph = (tw % 1.1) / 1.1
    w = np.where(ph < 0.4, 5.0 * np.sin(np.pi * ph / 0.4) ** 2, -1.2 * np.sin(np.pi * (ph - 0.4) / 0.6))
    axis = np.array([0.25, 0.92, 0.30]) / np.linalg.norm([0.25, 0.92, 0.30])
    tt = np.concatenate([tw, tw[-1] + 1 / fs + (t - t[0])])
    gg = np.vstack([np.outer(w, axis), gyro])
    assert "other_rhythm" in exp3.analyze_gyro(tt, gg, params)["flags"]


def test_strong_handling_does_not_hide_the_swing(params):
    # 정강이 폰을 숙여 켜고 끄는 동작(약 4 rad/s)이 흔들기(1.1 rad/s)보다 커도 흔들기 축을 찾는다
    # 무작위 합성 진자 40개 가운데 첫 축을 기록 전체로 구했을 때 흔들기를 놓친 경우(진폭이 줄어드는 흔들기)
    spec = SwingSpec(period_s=1.8987518581605007, omega_amp_rad_s=1.1022974460831647, handling_rad_s=3.8560808606817814,
                     swing_s=23.407073408680773, axis=(1.5112284332767216, 0.637533810897696, -0.6989304285787463),
                     decay_per_s=0.056761623769039815, noise_rad_s=0.02013533415356749, seed=37)
    t, gyro, _ = make_swing_gyro(spec)
    r = exp3.analyze_gyro(t, gyro, params)
    assert r["swing_period_s"] == pytest.approx(spec.period_s, rel=0.01)
    assert r["n_cycles_total"] >= 10
