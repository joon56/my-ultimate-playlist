"""수직 점프 (SPEC §4.6, §5.7, D-37, QA Q17). 합성 가속도에서 체공·이륙 속도·밀기 구간을 되찾는다."""

import numpy as np
import pytest

from walkmusic import jumps
from walkmusic.synthetic import JumpSpec, make_jump_imu


@pytest.fixture(scope="module")
def three(params):
    t, total, grav, truth = make_jump_imu(JumpSpec(seed=4), params["flight.a_thresh_g"], params["jump.landing_level_g"])
    return jumps.analyze_jumps(t, total, grav, params, mass_kg=60.0), truth


def test_three_jumps_found_in_order(three):
    rows, truth = three
    assert [r["jump_no"] for r in rows] == [1, 2, 3]
    for r, tr in zip(rows, truth, strict=True):
        # 사건 정의(D-77)대로의 이륙(0.2 g 아래로)·착지(1 g 위로)를 샘플 사이까지 되찾는다
        assert r["takeoff_s"] == pytest.approx(tr["takeoff_evt_s"], abs=0.006)
        assert r["landing_s"] == pytest.approx(tr["landing_evt_s"], abs=0.006)
        assert r["flight_time_s"] == pytest.approx(tr["flight_evt_s"], abs=0.006)
        # 이륙은 실제 이륙보다 몇 ms 앞, 착지는 지면반력이 체중에 닿는 때라 실제 닿음보다 늦다(합성 착지는 느리게 올라
        # 약 30 ms. 영상과 비교해 보고한다, D-38)
        assert 0 <= tr["takeoff_s"] - r["takeoff_s"] < 0.02
        assert 0 < r["flight_time_s"] - tr["flight_s"] < 0.06


def test_takeoff_velocity_two_ways(three, params):
    rows, truth = three
    g = params["constants.g"]
    for r, tr in zip(rows, truth, strict=True):
        assert r["takeoff_v_int_ms"] == pytest.approx(tr["v_evt_ms"], rel=0.015)  # 이륙 사건 시각까지 적분(정의)
        assert r["takeoff_v_int_ms"] == pytest.approx(tr["v_takeoff_ms"], rel=0.05)  # 실제 이륙 속도와 몇 % 안
        assert r["takeoff_v_flight_ms"] == pytest.approx(g * r["flight_time_s"] / 2)
        assert r["height_m"] == pytest.approx(g * r["flight_time_s"] ** 2 / 8)
        assert r["impulse_ns"] == pytest.approx(60.0 * r["takeoff_v_flight_ms"])


def test_pushoff_phase(three, params):
    rows, truth = three
    g = params["constants.g"]
    for r, tr in zip(rows, truth, strict=True):
        assert r["pushoff_time_s"] == pytest.approx(tr["pushoff_evt_s"], abs=0.02)
        assert r["mean_grf_push_bw"] == pytest.approx(1 + tr["v_evt_ms"] / (g * tr["pushoff_evt_s"]), rel=0.03)
        assert r["mean_grf_push_bw"] == pytest.approx(1 + r["takeoff_v_int_ms"] / (g * r["pushoff_time_s"]),
                                                      rel=0.01)  # SPEC §4.6: 평균 = 1 + v_int ÷ (g t_push)
        assert r["peak_grf_push_bw"] > r["mean_grf_push_bw"]


def test_jump_without_quiet_standing_is_not_counted(params):
    # D-77: 가만히 선 구간(PROTOCOL §3.7: 2초 가만히 선 뒤 뛴다)에서 시작하지 않은 사건은 점프로 세지 않는다
    t, total, grav, _ = make_jump_imu(JumpSpec(quiet_s=0.4, flight_times_s=(0.5,), seed=5))
    total[:, 2] += 0.08 * np.sin(2 * np.pi * 1.3 * t)  # 가만히 서지 못하고 계속 움직인다
    assert jumps.analyze_jumps(t, total, grav, params, mass_kg=60.0) == []


def test_phone_handling_is_not_a_jump(params):
    # 2026-11-20 시험: 기록 처음·끝에 폰을 만지는 흔들림이 밀기 → 0.2 g 아래 → 충격으로 보여 점프처럼 잡혔다.
    # 가만히 선 구간에서 시작하지 않아 세지 않고, 진짜 점프 번호는 1부터 그대로다(영상 jump_no와 맞춘다)
    spec = JumpSpec(seed=9)
    t, total, grav, truth = make_jump_imu(spec, params["flight.a_thresh_g"], params["jump.landing_level_g"])
    shake = (t >= 0.5) & (t < spec.handling_s - 0.3)
    total[shake, 2] += 1.5 * np.sin(2 * np.pi * 2.0 * t[shake])
    rows = jumps.analyze_jumps(t, total, grav, params, mass_kg=60.0)
    assert [r["jump_no"] for r in rows] == [1, 2, 3]
    assert [r["takeoff_s"] for r in rows] == pytest.approx([tr["takeoff_evt_s"] for tr in truth], abs=0.006)


def test_missing_mass_keeps_kinematics(params):
    t, total, grav, _ = make_jump_imu(JumpSpec(flight_times_s=(0.5,), seed=6))
    r = jumps.analyze_jumps(t, total, grav, params, mass_kg=float("nan"))[0]
    assert np.isfinite(r["height_m"]) and np.isnan(r["impulse_ns"])
    assert "no_mass" in r["flags"]


@pytest.mark.parametrize("n, status", [(3, "PASS"), (2, "WARN"), (4, "WARN"), (0, "FAIL")])
def test_q17_jump_count(params, n, status):
    assert jumps.q17_status(n, params) == status


def test_jump_long_after_quiet_is_not_counted(params):
    # 가만히 선 구간이 이륙보다 `jump.max_prejump_s` 넘게 앞이면(그 사이 움직임) 점프로 세지 않는다(검토 #7, D-77)
    spec = JumpSpec(quiet_s=8.0, flight_times_s=(0.5,), seed=7)
    t, total, grav, _ = make_jump_imu(spec)
    dip = spec.handling_s + spec.quiet_s
    sway = (t >= dip - 5.0) & (t < dip - 0.05)
    total[sway, 2] += 0.08 * np.sin(2 * np.pi * 1.3 * t[sway])
    assert jumps.analyze_jumps(t, total, grav, params, mass_kg=60.0) == []


def test_bouncy_flight_is_still_found(params):
    # 2026-11-20 A 시험: 공중에서 폰이 출렁여(파우치·팔 밴드) |a|가 0.2 g 아래에 머물지 않았다. 이륙 직후 수직 성분이
    # 음수로 꺾이고 옆 방향도 흔들린다. 사건 정의(D-77)는 이런 기록에서도 점프를 찾는다(옛 정의로는 0개)
    t, total, grav, truth = make_jump_imu(JumpSpec(seed=8), params["flight.a_thresh_g"], params["jump.landing_level_g"])
    for tr in truth:
        tau = t - tr["takeoff_s"]
        fl = (tau > 0) & (t < tr["landing_s"])
        total[fl, 2] += -0.5 * np.sin(2 * np.pi * 10 * tau[fl]) * np.exp(-tau[fl] / 0.2)
        total[fl, 0] += 0.4 * np.sin(2 * np.pi * 7 * tau[fl])
    rows = jumps.analyze_jumps(t, total, grav, params, mass_kg=60.0)
    assert len(rows) == 3
    for r, tr in zip(rows, truth, strict=True):
        assert r["takeoff_s"] == pytest.approx(tr["takeoff_evt_s"], abs=0.01)
        assert r["flight_time_s"] == pytest.approx(tr["flight_evt_s"], abs=0.01)


def test_running_steps_are_not_jumps(params):
    # 달리기 걸음(체공 약 0.1 s)은 이륙 뒤 첫 충격까지가 `jump.min_flight_s`보다 짧아 점프가 아니다
    from walkmusic.synthetic import TrialSpec, make_trial_imu

    t, f, g, _ = make_trial_imu(TrialSpec(cadence_spm=165, n_steps=60, run=True, flight_s=0.10, n_sync=0, seed=12))
    assert jumps.analyze_jumps(t, f, g, params, mass_kg=60.0) == []
