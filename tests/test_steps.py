"""걸음 검출 수용 기준(SPEC §5.4)과 출발·도착(D-29), 실제 파일 확인."""

import numpy as np
import pytest

from conftest import PRECHECK, TRIAL, real
from walkmusic.io_sensorlogger import read_zip
from walkmusic.steps import analyze_recording, cadence_summary, ml_dominant_hz
from walkmusic.units import total_accel_g

SIGNALS = ["magnitude", "vertical"]


@pytest.mark.parametrize("signal", SIGNALS)
@pytest.mark.parametrize("cadence", [90.0, 110.0, 130.0, 150.0])  # 걸음 주파수 1.5–2.5 Hz
@pytest.mark.parametrize("seed, noise, amp_cv", [(0, 0.02, 10.0), (1, 0.05, 20.0)])
def test_synthetic_cadence_within_1pct(make_synth, params, signal, cadence, seed, noise, amp_cv):
    path, truth = make_synth(walk_s=90, cadence_spm=cadence, seed=seed, noise_g=noise, amp_cv_pct=amp_cv)
    _, res = analyze_recording(read_zip(path), params, signal)
    s = cadence_summary(res, params)
    true_rate = (len(truth.step_times_s) - 1) / (truth.step_times_s[-1] - truth.step_times_s[0]) * 60
    assert s["cadence_rate_spm"] == pytest.approx(true_rate, rel=0.01)
    assert s["cadence_median_spm"] == pytest.approx(cadence, rel=0.01)
    assert abs(s["n_steps"] - len(truth.step_times_s)) <= params["qa.hand_count_tol_steps"]


@pytest.mark.parametrize("signal", SIGNALS)
@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
def test_standing_handling_and_prewalk_excluded(make_synth, params, signal, orientation):
    """서 있기 흔들림·폰 넣기·꺼내기·출발점까지 걷기는 걸음과 출발·도착에 들어가지 않는다."""
    path, truth = make_synth(walk_s=60, orientation=orientation, pre_walk_steps=14, fidget_bumps=3, seed=3)
    _, res = analyze_recording(read_zip(path), params, signal)
    assert res.t_depart == pytest.approx(truth.t_depart, abs=0.1)
    assert res.t_arrive == pytest.approx(truth.t_arrive, abs=0.1)
    assert res.stand_start is not None and res.stand_end is not None
    assert len(res.window_steps()) == pytest.approx(len(truth.step_times_s), abs=2)
    for a, b in (truth.stand_start, truth.stand_end):
        assert len(res.t_s[(res.t_s > a + 0.5) & (res.t_s < b - 0.5)]) == 0


@pytest.mark.parametrize("signal", SIGNALS)
def test_large_fidget_is_not_steps(make_synth, params, signal):
    """바지 주머니 시범처럼 서 있는 동안 큰 흔들림이 있어도 걸음으로 세지 않는다(D-48)."""
    path, truth = make_synth(walk_s=60, fidget_bumps=6, fidget_g=0.3, seed=5)
    _, res = analyze_recording(read_zip(path), params, signal)
    for a, b in (truth.stand_start, truth.stand_end):
        assert len(res.t_s[(res.t_s > a + 0.5) & (res.t_s < b - 0.5)]) == 0
    assert res.t_arrive == pytest.approx(truth.t_arrive, abs=0.1)


def test_ml_axis_half_step_frequency(make_synth, params):
    path, truth = make_synth(walk_s=90, cadence_spm=110.0, seed=4)
    rec = read_zip(path)
    t, total, g = total_accel_g(rec, analyze_recording(rec, params)[0])
    f = ml_dominant_hz(t, total, g, truth.t_depart, truth.t_arrive)
    assert f == pytest.approx(110.0 / 60 / 2, rel=0.1)


@pytest.mark.parametrize("signal", SIGNALS)
def test_real_100_steps(params, signal):
    _, res = analyze_recording(read_zip(real(PRECHECK[2])), params, signal)
    assert abs(len(res.window_steps()) - 100) <= params["qa.hand_count_tol_steps"]


@pytest.mark.parametrize("signal", SIGNALS)
def test_real_metronome_cadence(params, signal):
    _, res = analyze_recording(read_zip(real(PRECHECK[3])), params, signal)
    assert cadence_summary(res, params)["cadence_rate_spm"] == pytest.approx(100.0, rel=0.01)


def test_real_rehearsal_depart_arrive(params):
    _, res = analyze_recording(read_zip(real(PRECHECK[1])), params)
    assert res.t_depart == pytest.approx(29.9, abs=1.0) and res.t_arrive == pytest.approx(638.9, abs=1.0)


def test_real_trial_end_standing_has_no_steps(params):
    _, res = analyze_recording(read_zip(real(TRIAL)), params)
    assert len(res.t_s[(res.t_s > 701) & (res.t_s < 711)]) == 0
    assert "no_start_standing" in res.flags  # 시범은 시작에 서 있기가 없었다
    # 감속하던 마지막 걸음(간격이 중앙값의 1.4배 넘게 길어짐)은 steps.bout_split_frac로 잘릴 수 있다
    assert 698.0 <= res.t_arrive <= 700.5
    assert np.isclose(len(res.window_steps()), 1179, atol=10)
