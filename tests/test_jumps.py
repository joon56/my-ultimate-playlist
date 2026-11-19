"""수직 점프 (SPEC §4.6, §5.7, D-37, QA Q17). 합성 가속도에서 체공·이륙 속도·밀기 구간을 되찾는다."""

import numpy as np
import pytest

from walkmusic import jumps
from walkmusic.synthetic import JumpSpec, make_jump_imu


@pytest.fixture(scope="module")
def three(params):
    t, total, grav, truth = make_jump_imu(JumpSpec(seed=4))
    return jumps.analyze_jumps(t, total, grav, params, mass_kg=60.0), truth


def test_three_jumps_found_in_order(three):
    rows, truth = three
    assert [r["jump_no"] for r in rows] == [1, 2, 3]
    for r, tr in zip(rows, truth, strict=True):
        # 정의(0.2 g 문턱)대로의 이륙·체공을 샘플 사이까지 되찾는다
        assert r["flight_time_s"] == pytest.approx(tr["flight_thr_s"], abs=0.006)
        assert r["takeoff_s"] == pytest.approx(tr["takeoff_thr_s"], abs=0.006)
        # 문턱은 실제 이륙 직전·착지 직후에 지나므로 실제 체공보다 조금 길다(영상과 비교해 보고한다, D-38)
        assert 0 < r["flight_time_s"] - tr["flight_s"] < 0.025


def test_takeoff_velocity_two_ways(three, params):
    rows, truth = three
    g = params["constants.g"]
    for r, tr in zip(rows, truth, strict=True):
        assert r["takeoff_v_int_ms"] == pytest.approx(tr["v_thr_ms"], rel=0.015)  # 문턱 시각까지 적분(정의)
        assert r["takeoff_v_int_ms"] == pytest.approx(tr["v_takeoff_ms"], rel=0.05)  # 실제 이륙 속도와는 약 3% 차이
        # 두 방법(체공, 적분)이 같은 쪽으로 치우친다
        assert r["takeoff_v_int_ms"] == pytest.approx(r["takeoff_v_flight_ms"], rel=0.03)
        assert r["takeoff_v_flight_ms"] == pytest.approx(g * r["flight_time_s"] / 2)
        assert r["height_m"] == pytest.approx(g * r["flight_time_s"] ** 2 / 8)
        assert r["impulse_ns"] == pytest.approx(60.0 * r["takeoff_v_flight_ms"])


def test_pushoff_phase(three, params):
    rows, truth = three
    g = params["constants.g"]
    for r, tr in zip(rows, truth, strict=True):
        assert r["pushoff_time_s"] == pytest.approx(tr["pushoff_thr_s"], abs=0.02)
        assert r["mean_grf_push_bw"] == pytest.approx(1 + tr["v_thr_ms"] / (g * tr["pushoff_thr_s"]), rel=0.03)
        assert r["mean_grf_push_bw"] == pytest.approx(1 + r["takeoff_v_int_ms"] / (g * r["pushoff_time_s"]),
                                                      rel=0.01)  # SPEC §4.6: 평균 = 1 + v_int ÷ (g t_push)
        assert r["peak_grf_push_bw"] > r["mean_grf_push_bw"]


def test_no_quiet_standing_is_flagged(params):
    t, total, grav, _ = make_jump_imu(JumpSpec(quiet_s=0.4, flight_times_s=(0.5,), seed=5))
    total[:, 2] += 0.08 * np.sin(2 * np.pi * 1.3 * t)  # 가만히 서지 못하고 계속 움직인다
    r = jumps.analyze_jumps(t, total, grav, params, mass_kg=60.0)[0]
    assert np.isnan(r["takeoff_v_int_ms"])
    assert "no_quiet" in r["flags"]


def test_missing_mass_keeps_kinematics(params):
    t, total, grav, _ = make_jump_imu(JumpSpec(flight_times_s=(0.5,), seed=6))
    r = jumps.analyze_jumps(t, total, grav, params, mass_kg=float("nan"))[0]
    assert np.isfinite(r["height_m"]) and np.isnan(r["impulse_ns"])
    assert "no_mass" in r["flags"]


@pytest.mark.parametrize("n, status", [(3, "PASS"), (2, "WARN"), (4, "WARN"), (0, "FAIL")])
def test_q17_jump_count(params, n, status):
    assert jumps.q17_status(n, params) == status


def test_quiet_long_before_jump_is_not_integrated(params):
    # 가만히 선 구간이 이륙보다 한참 전이면(그 사이 움직임) 적분하지 않고 표시한다(검토 #7)
    spec = JumpSpec(quiet_s=8.0, flight_times_s=(0.5,), seed=7)
    t, total, grav, _ = make_jump_imu(spec)
    dip = spec.handling_s + spec.quiet_s
    sway = (t >= dip - 5.0) & (t < dip - 0.05)
    total[sway, 2] += 0.08 * np.sin(2 * np.pi * 1.3 * t[sway])
    r = jumps.analyze_jumps(t, total, grav, params, mass_kg=60.0)[0]
    assert np.isnan(r["takeoff_v_int_ms"])
    assert "quiet_far" in r["flags"]
    assert np.isfinite(r["height_m"])  # 체공 기반 값은 그대로 낸다
