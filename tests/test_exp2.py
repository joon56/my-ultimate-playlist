"""실험 2 템포 챌린지 (SPEC §4.4–4.6, §5.7, D-13·D-39·D-54·D-56·D-57). 합성 시행에서 정답을 되찾는다."""

import numpy as np
import pandas as pd
import pytest

from walkmusic import exp2
from walkmusic.synthetic import TrialSpec, make_trial_imu


def test_exp2_params_lower_interval_only(params):
    p2 = exp2.exp2_params(params)
    assert p2["steps.min_interval_s"] == params["exp2.min_interval_s"]
    assert params["steps.min_interval_s"] == 0.30  # 원본은 그대로(실험 1은 0.30 s, D-56)


def test_central_window():
    s = np.arange(100) * 0.5
    assert exp2.central_window(s, 0.75) == (s[12], s[87])


@pytest.fixture(scope="module")
def walk_trial(params):
    t, f, g, truth = make_trial_imu(TrialSpec(cadence_spm=130, n_steps=60, seed=7))
    return exp2.analyze_trial(t, f, g, params, bpm=130.0), truth


def test_walking_trial_cadence_and_sync(walk_trial):
    r, _ = walk_trial
    assert r["cadence_median_spm"] == pytest.approx(130, rel=0.01)
    assert r["sync3_pct"] >= 80
    assert r["flight_step_frac"] == 0
    assert r["sensor_gait"] == "walk"
    assert r["window_method"] == "central_steps"
    assert "central_steps" in r["flags"]  # D-13 대안을 쓴 시행은 표시한다
    assert r["n_steps_window"] == pytest.approx(0.75 * 60, abs=2)


def test_sync_jumps_found(walk_trial):
    r, truth = walk_trial
    assert r["n_sync_jumps"] == 3
    got = [float(x) for x in r["sync_jump_sensor_s"].split(";")]  # SPEC §5.7의 열 이름
    assert got == pytest.approx(truth["sync_landing_s"], abs=0.02)


def test_video_window_used_when_given(params):
    t, f, g, truth = make_trial_imu(TrialSpec(seed=8))
    st = truth["step_times_s"]
    r = exp2.analyze_trial(t, f, g, params, bpm=130.0, t_in=st[10] - 0.05, t_out=st[40] + 0.05)
    assert r["window_method"] == "video"
    assert r["n_steps_window"] == 31


def test_fast_running_trial_flight_and_contact(params):
    # 240 BPM(간격 0.25 s)에 맞춰 뛰어도 걸음이 걸러지지 않는다(D-56의 0.23 s 하한)
    t, f, g, truth = make_trial_imu(TrialSpec(cadence_spm=240, n_steps=50, run=True, flight_s=0.08, seed=9))
    r = exp2.analyze_trial(t, f, g, params, bpm=240.0)
    assert r["cadence_median_spm"] == pytest.approx(240, rel=0.01)
    assert r["sensor_gait"] == "run"
    assert r["flight_step_frac"] >= 0.95
    assert r["flight_time_median_s"] == pytest.approx(truth["flight_thr_s"], abs=0.006)
    assert r["contact_time_s"] == pytest.approx(truth["contact_thr_s"], abs=0.006)


def _stage(runner, ratio, rep, **kw):
    base = dict(runner=runner, ratio_pct=str(ratio), repeat=rep, bpm_played=float(ratio), tempo_ratio_pct=float(ratio),
                v_ms=1.5, cadence_median_spm=float(ratio), sync3_pct=90.0, gait_video="walk", flags="")
    base.update(kw)
    return base


def test_stage_summary_uses_mean_speed_for_froude(params):
    tr = pd.DataFrame([_stage("A", 150, 1, v_ms=2.0, sync3_pct=60.0), _stage("A", 150, 2, v_ms=2.2, sync3_pct=70.0)])
    s = exp2.stage_summary(tr, {"A": 0.9}, params)
    row = s.iloc[0]
    assert row["v_ms"] == pytest.approx(2.1)
    assert row["fr"] == pytest.approx(2.1**2 / (params["constants.g"] * 0.9))  # 두 시행 평균 속도로(D-57)
    assert row["sync3_pct"] == pytest.approx(65.0)
    assert row["n_trials"] == 2


def test_h3_rules_d57(params):
    g, leg = params["constants.g"], 0.9
    v_for = {0.40: np.sqrt(0.40 * g * leg), 0.55: np.sqrt(0.55 * g * leg)}
    rows = []
    for rep in (1, 2):  # A: 150%에서 한 시행이 run → 처음 뛴 단계 150, 마지막으로 걸은 단계 135
        rows += [_stage("A", 100, rep), _stage("A", 120, rep), _stage("A", 135, rep, v_ms=v_for[0.40]),
                 _stage("A", 150, rep, v_ms=v_for[0.55], gait_video="run" if rep == 1 else "walk")]
        rows += [_stage("B", r, rep) for r in (100, 120, 135, 150, 165)]  # B: 끝까지 걸음
        rows += [_stage("C", 100, rep), _stage("C", 120, rep, gait_video="mixed"), _stage("C", 135, rep)]
    tr = pd.DataFrame(rows)
    s = exp2.stage_summary(tr, {"A": leg, "B": leg, "C": leg}, params)
    h = {r["participant"]: r for r in exp2.h3_rows(tr, s, params)}
    assert h["A"]["supported"] is True
    assert h["B"]["supported"] == "NA" and "no_run" in h["B"]["note"]
    assert "non_monotonic" in h["C"]["note"]


def test_h1_2_needs_both_100_and_120(params):
    rows = []
    for rep in (1, 2):
        rows += [_stage("A", 100, rep, sync3_pct=85.0), _stage("A", 120, rep, sync3_pct=82.0)]
        rows += [_stage("B", 100, rep, sync3_pct=90.0), _stage("B", 120, rep, sync3_pct=70.0)]
        rows += [_stage("C", 100, rep, sync3_pct=90.0)]
    tr = pd.DataFrame(rows)
    s = exp2.stage_summary(tr, {}, params)
    h = {r["participant"]: r["supported"] for r in exp2.h12_rows(s, params)}
    assert h == {"A": True, "B": False, "C": "NA"}


def test_prescription_upper_example_19(params):
    # SPEC §9 #19: 단계 S3와 (단계 케이던스 ÷ bpm_played − 1)
    s3 = {100: 95, 120: 88, 135: 82, 150: 64, 165: 31}
    dev = {100: 0.4, 120: -1.1, 135: -2.0, 150: -2.8, 165: -9.5}
    s = pd.DataFrame([dict(runner="A", ratio_pct=str(r), tempo_ratio_pct=float(r), bpm_played=110 * r / 100,
                           cadence_median_spm=110 * r / 100 * (1 + dev[r] / 100), sync3_pct=float(s3[r]))
                      for r in s3])
    up = exp2.prescription_upper(s, params).set_index("runner").loc["A"]
    assert up["t_high_pct"] == 150
    assert up["t_high_s3_pct"] == 135


@pytest.mark.parametrize("label, want", [("walk", "walk"), ("걷기", "walk"), (" W ", "walk"), ("run", "run"),
                                         ("뛰기", "run"), ("달리기", "run"), ("R", "run"), ("mixed", "mixed"),
                                         ("섞임", "mixed"), ("", ""), ("뛴듯", "unknown")])
def test_gait_labels_normalized(label, want):
    # PROTOCOL 3.5는 '걷기/뛰기(영상 판정)'라 기록지에 한글로 적을 수 있다(검토 #3)
    assert exp2.normalize_gait(label) == want


def _h3_set(lab):
    g, leg = 9.81, 0.9
    v_for = {0.40: np.sqrt(0.40 * g * leg), 0.55: np.sqrt(0.55 * g * leg)}
    rows = []
    for rep in (1, 2):
        rows += [_stage("A", 100, rep, gait_video=lab["walk"]), _stage("A", 120, rep, gait_video=lab["walk"]),
                 _stage("A", 135, rep, v_ms=v_for[0.40], gait_video=lab["walk"]),
                 _stage("A", 150, rep, v_ms=v_for[0.55], gait_video=lab["run"] if rep == 1 else lab["walk"])]
    return pd.DataFrame(rows)


def test_h3_same_with_korean_labels(params):
    for lab in ({"walk": "walk", "run": "run"}, {"walk": "걷기", "run": "뛰기"}):
        tr = _h3_set(lab)
        s = exp2.stage_summary(tr, {"A": 0.9}, params)
        assert exp2.h3_rows(tr, s, params)[0]["supported"] is True
        assert s.set_index("ratio_pct").loc["150", "gait_video"] == "mixed"


def test_h3_without_any_labels_is_not_reported_as_no_run(params):
    tr = _h3_set({"walk": "", "run": ""})
    s = exp2.stage_summary(tr, {"A": 0.9}, params)
    row = exp2.h3_rows(tr, s, params)[0]
    assert row["supported"] == "NA"
    assert "no_run" not in row["note"] and "영상 판정" in row["note"]


def test_prescription_upper_skips_stage_with_missing_values(params):
    # §9 #19에서 120% 단계 값이 비면 '깨짐'이 아니라 '모름'으로 건너뛴다(검토 #4)
    s3 = {100: 95, 120: np.nan, 135: 82, 150: 64, 165: 31}
    dev = {100: 0.4, 120: np.nan, 135: -2.0, 150: -2.8, 165: -9.5}
    s = pd.DataFrame([dict(runner="A", ratio_pct=str(r), tempo_ratio_pct=float(r), bpm_played=110 * r / 100,
                           cadence_median_spm=110 * r / 100 * (1 + dev[r] / 100), sync3_pct=float(s3[r]))
                      for r in s3])
    up = exp2.prescription_upper(s, params).set_index("runner").loc["A"]
    assert (up["t_high_pct"], up["t_high_s3_pct"]) == (150, 135)
    assert "missing_120" in up["flags"]


def test_stage_values_are_pooled_step_medians(params):
    tr = pd.DataFrame([_stage("A", 165, 1, trial_id="t1", flight_time_median_s=0.10, contact_time_s=0.20,
                              gait_video="run"),
                       _stage("A", 165, 2, trial_id="t2", flight_time_median_s=0.14, contact_time_s=0.16,
                              gait_video="run")])
    phases = {"t1": (np.array([0.10, 0.10, 0.10]), np.array([0.20, 0.20, 0.20])),
              "t2": (np.array([0.14]), np.array([0.16]))}
    s = exp2.stage_summary(tr, {"A": 0.9}, params, body={"A": {"mass_kg": 60.0}}, phases=phases).iloc[0]
    assert s["flight_time_median_s"] == pytest.approx(0.10)  # 걸음을 모은 중앙값(평균 0.12가 아니다, SPEC §4.6)
    assert s["contact_time_s"] == pytest.approx(0.20)
