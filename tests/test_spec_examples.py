"""SPEC §9 예제 수치 (DECISIONS D-41: #7·#8 제외)."""

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
