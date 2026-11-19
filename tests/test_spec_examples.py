"""SPEC §9 예제 수치 (DECISIONS D-53: #7·#8 제외)."""

import math

import numpy as np
import pytest

from walkmusic import metrics as m
from walkmusic.config import load_params

P = load_params()
G = P["constants.g"]


def test_01_speed_cadence_step_length():
    v = m.speed_mps(200, 150)
    c = m.cadence_from_count(275, 150)
    assert v == pytest.approx(1.3333, abs=1e-4)
    assert c == pytest.approx(110.0)
    assert m.step_length_m(v, c) == pytest.approx(0.7273, abs=1e-4)


def test_02_tempo_ratio_and_bands():
    assert m.tempo_ratio_pct(120, 110) == pytest.approx(109.09, abs=0.005)
    assert m.tolerance_band(120, P["sync.tol_pct"]) == pytest.approx((116.4, 123.6))
    assert m.tolerance_band(120, P["sync.tol_alt_pct"]) == pytest.approx((114.0, 126.0))


def test_03_dc_and_follow_ratio():
    dc = m.cadence_change_pct(115, 110)
    t = m.tempo_ratio_pct(120, 110)
    assert dc == pytest.approx(4.545, abs=5e-4)
    assert t - 100 == pytest.approx(9.091, abs=5e-4)
    assert m.follow_ratio(dc, t, P["sync.r_exclude_low"], P["sync.r_exclude_high"]) == pytest.approx(0.5)
    assert math.isnan(m.follow_ratio(1.0, 101.0, P["sync.r_exclude_low"], P["sync.r_exclude_high"]))


def test_04_force_over_bodyweight():
    a_total = G + 3.0
    assert m.vertical_force_n(60, a_total) == pytest.approx(768.6)
    assert m.vertical_force_n(60, G) == pytest.approx(588.6)
    assert m.force_over_bodyweight(a_total, G) == pytest.approx(1.306, abs=5e-4)


def test_05_froude():
    assert math.sqrt(G * 0.9) == pytest.approx(2.971, abs=5e-4)
    assert m.speed_at_froude(P["stats.froude_walk_run"], 0.9, G) == pytest.approx(2.101, abs=5e-4)
    assert m.froude(1.33, 0.9, G) == pytest.approx(0.2004, abs=5e-5)


def test_06_rise_height():
    assert m.rise_height_m(0.12, G) == pytest.approx(0.01766, abs=5e-6)


def test_09_pendulum():
    pm = m.pendulum_period_model_s(0.9, P["pendulum.k_over_L"], P["pendulum.d_over_L"], G)
    assert pm == pytest.approx(1.5940, abs=5e-5)
    assert m.pendulum_cadence_spm(pm) == pytest.approx(75.28, abs=5e-3)
    assert m.pendulum_cadence_spm(1.6) == pytest.approx(75.0)


def test_10_log_decomposition():
    r = m.log_speed_decomposition(1.30, 1.45, 108, 116)
    assert r["step_length_0_m"] == pytest.approx(0.7222, abs=5e-5)
    assert r["step_length_1_m"] == pytest.approx(0.7500, abs=5e-5)
    assert r["dln_v"] == pytest.approx(0.10920, abs=5e-6)
    assert r["dln_c"] == pytest.approx(0.07146, abs=5e-6)
    assert r["dln_sl"] == pytest.approx(0.03774, abs=5e-6)
    assert r["contrib_cadence"] == pytest.approx(0.6544, abs=5e-5)
    assert r["contrib_step_length"] == pytest.approx(0.3456, abs=5e-5)
    assert r["dln_v"] == pytest.approx(r["dln_c"] + r["dln_sl"])


def test_11_sync_counts():
    r = m.sync_counts([118, 121, 124, 119, 100, 240, 60.5], 120, P["sync.tol_pct"])
    assert (r["n_sync"], r["n"]) == (3, 7)
    assert r["sync_pct"] == pytest.approx(42.86, abs=5e-3)
    assert (r["n_half"], r["n_double"]) == (1, 1)


def test_12_13_cv():
    assert m.cv_pct([0.50, 0.52, 0.48, 0.50, 0.50], P["stats.sd_ddof"]) == pytest.approx(2.828, abs=5e-4)
    assert m.cv_pct([108, 110, 112], P["stats.sd_ddof"]) == pytest.approx(1.818, abs=5e-4)


def test_14_tempo_files():
    step = P["music.tempo_file_step_bpm"]
    got = [m.tempo_file_bpm(110, r, step) for r in (1.00, 1.20, 1.35, 1.50, 1.65)]
    assert got == [110, 130, 150, 165, 180]
    # PROTOCOL 3.4 조회표 전체(0.5는 올림)
    table = {100: [100, 120, 135, 150, 165], 105: [105, 125, 140, 160, 175], 115: [115, 140, 155, 175, 190],
             120: [120, 145, 160, 180, 200], 125: [125, 150, 170, 190, 205]}
    for pc, want in table.items():
        assert [m.tempo_file_bpm(pc, r / 100, step) for r in P["exp2.stage_ratios_pct"]] == want


@pytest.mark.parametrize("n_low, n_events", [(5, 1), (3, 1), (2, 0)])
def test_15_flight_events(n_low, n_events):
    sig = np.ones(200)
    sig[100:100 + n_low] = 0.1
    ev = m.flight_events(sig, 100.0, P["flight.a_thresh_g"], P["flight.min_duration_s"])
    assert len(ev) == n_events
    assert m.min_flight_samples(100.0, 0.030) == 3
    assert m.min_flight_samples(50.0, 0.030) == 2


def test_16_tempo_file_count():
    assert m.tempo_file_count(100, 210, P["music.tempo_file_step_bpm"]) == 23


def test_17_near_pc_band():
    assert m.tolerance_band(110, P["sync.near_pc_pct"]) == pytest.approx((99.0, 121.0))


SEG = {k: P[f"pendulum.seg_{k}_frac"] for k in ("thigh_mass", "thigh_com", "thigh_kcm",
                                                 "shank_mass", "shank_com", "shank_kcm")}


def test_21_jump_from_flight_time():
    r = m.jump_from_flight(0.50, 60, G)
    assert r["height_m"] == pytest.approx(0.30656, abs=5e-6)
    assert r["takeoff_v_ms"] == pytest.approx(2.4525, abs=5e-5)
    assert r["impulse_ns"] == pytest.approx(147.15, abs=5e-3)
    assert r["kinetic_energy_j"] == pytest.approx(180.44, abs=5e-3)
    assert r["kinetic_energy_j"] == pytest.approx(60 * G * r["height_m"])  # ½mv² = mgh


def test_22_pushoff_mean_force():
    bw = m.pushoff_mean_grf_bw(2.4525, 0.30, G)
    assert bw == pytest.approx(1.8333, abs=5e-5)
    assert bw * 60 * G == pytest.approx(1079.1, abs=0.05)


def test_23_video_frames():
    tf = m.frames_to_seconds(120, 240)
    assert tf == pytest.approx(0.5)
    assert m.rise_height_m(tf, G) * 100 == pytest.approx(30.66, abs=5e-3)
    assert m.height_per_frame_m(tf, 240, G) * 100 == pytest.approx(0.51, abs=5e-3)
    assert m.height_per_frame_m(tf, 120, G) * 100 == pytest.approx(1.02, abs=5e-3)


def test_24_running_flight_parabola():
    r = m.running_flight(2.5, 0.10, G)
    assert r["vertical_v_ms"] == pytest.approx(0.4905, abs=5e-5)
    assert r["takeoff_angle_deg"] == pytest.approx(11.10, abs=5e-3)
    assert r["air_distance_m"] == pytest.approx(0.250)
    assert r["rise_height_m"] * 100 == pytest.approx(1.226, abs=5e-4)


def test_25_spring_mass_running():
    r = m.spring_mass(60, 0.25, 0.10, 3.0, 0.90, G)
    assert r["fmax_n"] == pytest.approx(1294.4, abs=0.05)
    assert r["fmax_bw"] == pytest.approx(2.199, abs=5e-4)
    assert r["delta_y_m"] == pytest.approx(0.05997, abs=5e-6)
    assert r["delta_l_m"] == pytest.approx(0.14182, abs=5e-6)
    assert r["kvert_kn_m"] == pytest.approx(21.58, abs=5e-3)
    assert r["kleg_kn_m"] == pytest.approx(9.13, abs=5e-3)
    assert r["elastic_energy_j"] == pytest.approx(38.8, abs=0.05)
    assert r["mean_grf_contact_bw"] == pytest.approx(1.40)


def test_26_segment_pendulum_straight_and_bent():
    s = m.segment_pendulum(60, 0.4165, 0.4182, 0.0, G, SEG)
    b = m.segment_pendulum(60, 0.4165, 0.4182, 90.0, G, SEG)
    assert s["mass_kg"] == pytest.approx(9.66)
    assert s["inertia_hip_kgm2"] == pytest.approx(2.057, abs=5e-4)
    assert s["com_dist_m"] == pytest.approx(0.366, abs=5e-4)
    assert s["period_s"] == pytest.approx(1.531, abs=5e-4)
    assert m.pendulum_cadence_spm(s["period_s"]) == pytest.approx(78.4, abs=0.05)
    assert b["inertia_hip_kgm2"] == pytest.approx(1.284, abs=5e-4)
    assert (b["inertia_hip_kgm2"] / s["inertia_hip_kgm2"] - 1) * 100 == pytest.approx(-37.6, abs=0.05)
    assert b["com_dist_m"] == pytest.approx(0.286, abs=5e-4)
    assert b["period_s"] == pytest.approx(1.367, abs=5e-4)
    assert (b["period_s"] / s["period_s"] - 1) * 100 == pytest.approx(-10.7, abs=0.05)
    assert m.pendulum_cadence_spm(b["period_s"]) == pytest.approx(87.8, abs=0.05)
    assert b["period_s"] / s["period_s"] == pytest.approx(0.893, abs=5e-4)


def test_27_pendulum_energy_and_torque():
    s = m.segment_pendulum(60, 0.4165, 0.4182, 0.0, G, SEG)
    r = m.pendulum_energy(s["mass_kg"], s["com_dist_m"], s["inertia_hip_kgm2"], 30.0, G)
    assert r["potential_energy_j"] == pytest.approx(4.645, abs=5e-4)
    assert r["omega_pred_rad_s"] == pytest.approx(2.125, abs=5e-4)
    assert (0.4165 + 0.4182) * r["omega_pred_rad_s"] == pytest.approx(1.774, abs=5e-4)
    assert r["gravity_torque_nm"] == pytest.approx(17.33, abs=5e-3)
    assert r["angular_accel_rad_s2"] == pytest.approx(8.43, abs=5e-3)


def test_28_knee_angles_from_markers():
    r = m.knee_angles((0, 0), (50, 420), (-100, 800))
    assert r["knee_inner_deg"] == pytest.approx(151.67, abs=5e-3)
    assert r["knee_flexion_deg"] == pytest.approx(28.33, abs=5e-3)
    assert r["leg_angle_deg"] == pytest.approx(-7.13, abs=5e-3)


def test_29_inverted_pendulum_step_length():
    sl = m.step_length_zh(0.90, 0.040, P["com.zh_correction"])
    assert sl == pytest.approx(0.5307, abs=5e-5)
    assert sl / m.step_length_m(m.speed_mps(200, 150), 110) == pytest.approx(0.7297, abs=5e-5)


def test_30_bland_altman():
    r = m.bland_altman([110, 112, 115, 120], [111, 112, 113, 121], P["stats.sd_ddof"])
    assert r["n"] == 4
    assert r["bias"] == pytest.approx(0.0)
    assert r["sd"] == pytest.approx(1.414, abs=5e-4)
    assert (r["loa_low"], r["loa_high"]) == pytest.approx((-2.772, 2.772), abs=5e-4)


def test_31_extra_stage_tempo_files():
    step = P["music.tempo_file_step_bpm"]
    assert [m.tempo_file_bpm(110, r, step) for r in (1.80, 1.95)] == [200, 215]
    assert [m.tempo_file_bpm(112, r, step) for r in (1.80, 1.95)] == [200, 220]
