"""실험 2·3 파이프라인을 합성 자료로 처음부터 끝까지 (SPEC §5.7–5.8, §7, §10)."""

import pandas as pd
import pytest

from walkmusic.exp23 import Paths23, field_report, make_synthetic_exp23, run_exp23


@pytest.fixture(scope="module")
def res(tmp_path_factory, params):
    root = tmp_path_factory.mktemp("exp23")
    truth = make_synthetic_exp23(root, params)
    paths = Paths23.under(root)
    return run_exp23(paths, params, real=False), paths, truth


def _hyp(res, h):
    return {r["participant"]: r["supported"] for r in res[0]["hypotheses"] if r["hypothesis"] == h}


def test_all_trials_processed(res):
    out, paths, _ = res
    tr = out["trials"]
    assert len(tr) == 36  # 3명 × (무음 2 + 5단계 × 2)
    assert set(tr["window_method"]) == {"central_steps"}
    assert not [q for q in out["qa"] if q["status"] == "FAIL"]


def test_field_pc_recomputed_from_silent_trials(res):
    out, _, truth = res
    pcs = out["pcs"].set_index("runner")
    for p, pc in truth["pc"].items():
        assert pcs.loc[p, "pc_field_spm"] == pytest.approx(pc, abs=1.0)


def test_hypotheses(res):
    assert _hyp(res, "H1-2") == {"A": True, "B": True, "C": True, "ALL": True}
    h3 = _hyp(res, "H3")
    assert h3["A"] is True and h3["C"] is True and h3["B"] == "NA"
    assert _hyp(res, "H4") == {"A": True, "B": True, "C": True, "ALL": True}


def test_jumps_and_q17(res):
    out, _, truth = res
    js = out["jumps"]
    assert len(js) == 9
    assert [q["status"] for q in out["qa"] if q["check_id"] == "Q17"] == ["PASS"] * 3
    a = js[js["runner"] == "A"]
    assert a["flight_time_video_s"].notna().all()


def test_pendulum_periods_and_knee_angle(res):
    out, _, truth = res
    sw = out["swings"].set_index("trial_id")
    for tid, period in truth["periods"].items():
        assert sw.loc[tid, "swing_period_s"] == pytest.approx(period, rel=0.01)
    assert sw.loc["E3_A_K_1", "knee_deg"] == pytest.approx(85.0, abs=0.05)  # 영상 마커
    # 굽힌 다리는 3회 중 1회만 찍는다(PROTOCOL 4.5): 같은 사람의 찍은 시행 각도를 쓴다
    assert sw.loc["E3_A_K_2", "knee_deg"] == pytest.approx(85.0, abs=0.05)
    assert "knee_from_other_trial" in sw.loc["E3_A_K_2", "flags"]
    assert "knee_nominal" in sw.loc["E3_B_K_1", "flags"]
    assert "seg_len_from_height" in sw.loc["E3_B_1", "flags"]  # B는 허벅지·정강이를 안 쟀다


def test_prescription_upper_filled(res):
    _, paths, _ = res
    pres = pd.read_csv(paths.results / "prescription.csv")
    a = pres[(pres["participant"] == "A") & (pres["row_type"] == "summary")].iloc[0]
    assert a["t_high_pct"] > 100


def test_no_coordinates_in_outputs(res):
    _, paths, _ = res
    for f in paths.results.glob("*.csv"):
        cols = {c.lower() for c in pd.read_csv(f, nrows=0).columns}
        assert not cols & {"latitude", "longitude", "lat", "lon"}, f.name


def test_field_report_lists_trials(res):
    text = field_report(res[0])
    assert "E2_A_150_1" in text and "E3_C_K_3" in text


def test_link_proposal_by_recording_order(tmp_path, params):
    from walkmusic.exp23 import propose_links23

    root = tmp_path / "links"
    make_synthetic_exp23(root, params)
    paths = Paths23.under(root)
    want = {}
    for name in ("exp2_trials.csv", "exp3_swings.csv"):  # 기록지의 zip_file을 비운다
        sheet = pd.read_csv(paths.data / name, dtype=str, keep_default_na=False)
        want.update(dict(zip(sheet["trial_id"], sheet["zip_file"], strict=True)))
        sheet["zip_file"] = ""
        sheet.to_csv(paths.data / name, index=False)
    links = propose_links23(paths, params)
    got = dict(zip(links["trial_id"], links["zip_name"], strict=True))
    assert got == want
    assert set(links["status"]) == {"ok"}
    kinds = dict(zip(links["trial_id"], links["detected_kind"], strict=True))
    assert kinds["E2_A_J_1"] == "jump" and kinds["E3_B_K_2"] == "swing" and kinds["E2_C_150_1"] == "trial"


def test_waist_gait_rotation_is_not_taken_as_swing(tmp_path, params):
    # 허리 파우치 달리기: 골반이 세로축(중력 방향)으로 크게 돌아도(ω 2.7 rad/s) 진자가 아니다.
    # 다리 흔들기는 수평축으로 돈다(D-73, 2026-11-20 혼자 시험: 흔들기 72–74°, 걷기·달리기 3–14°)
    import numpy as np

    from walkmusic.exp23 import _detect_kind
    from walkmusic.synthetic import FRAMES, TrialSpec, make_trial_imu, write_imu_zip

    t, f, _, _ = make_trial_imu(TrialSpec(cadence_spm=165, n_steps=80, run=True, n_sync=0, seed=21))
    up = FRAMES["landscape"] @ np.array([0.0, 0.0, 1.0])  # 몸 위쪽을 폰 좌표로(write_imu_zip 기본 방향)
    gyro = np.outer(2.7 * np.sin(2 * np.pi * (165 / 60 / 2) * t), up)  # 한 보(두 걸음) 주기의 골반 회전
    write_imu_zip(tmp_path / "run.zip", t, f, gyro=gyro)
    assert _detect_kind(tmp_path / "run.zip", params)[0] == "trial"


def test_gentle_swing_is_still_swing(tmp_path, params):
    # 작게 흔든 진자(ω 봉우리 1 rad/s 미만, 2026-11-20 재시험 test-swing-2 0.74·test-swing-bent-2 0.81 rad/s)도 swing.
    # 걷기·달리기는 회전축 조건으로 거르므로 각속도 기준은 분석 바닥값 수준이면 된다(D-73)
    import numpy as np

    from walkmusic.exp23 import _detect_kind
    from walkmusic.synthetic import SwingSpec, make_swing_gyro, write_imu_zip

    t, gyro, _ = make_swing_gyro(SwingSpec(period_s=1.45, omega_amp_rad_s=0.8, swing_s=25.0, seed=31))
    write_imu_zip(tmp_path / "gentle.zip", t, np.tile([0.0, 0.0, 1.0], (len(t), 1)), gyro=gyro)
    assert _detect_kind(tmp_path / "gentle.zip", params)[0] == "swing"


@pytest.fixture(scope="module")
def messy(tmp_path_factory, params):
    """현장 기록지가 덜 채워졌거나 틀린 경우(독립 검토 #1·#2·#3·#5와 작은 문제들)."""
    import numpy as np

    root = tmp_path_factory.mktemp("messy")
    make_synthetic_exp23(root, params)
    paths = Paths23.under(root)
    s2 = pd.read_csv(paths.data / "exp2_trials.csv", dtype=str, keep_default_na=False)

    def setv(tid, col, val):
        s2.loc[s2["trial_id"] == tid, col] = val

    setv("E2_A_150_1", "zip_file", "")  # 뛴 시행의 zip이 없다 → 영상 값(t30, N, 판정)은 남아야 한다
    setv("E2_B_S_1", "zip_file", "")  # 무음 zip이 없다 → 현장 PC는 기록지 값으로 낸다
    kor = {"walk": "걷기", "run": "뛰기", "mixed": "섞임"}
    c = s2["runner"] == "C"
    s2.loc[c, "gait_video"] = s2.loc[c, "gait_video"].map(lambda g: kor.get(g, g))  # C는 한글로 적었다
    setv("E2_A_165_2", "zip_file", "E2_A_165_1.zip")  # 같은 zip을 두 줄에
    setv("E2_C_100_2", "t30_s", "0")  # 0으로 잘못 적었다
    s2["valid"] = ""  # 선택 열: 0이면 뺀다
    setv("E2_B_120_2", "valid", "0")
    s2.to_csv(paths.data / "exp2_trials.csv", index=False)
    (paths.raw / "C" / "E2_C_100_2.zip").write_bytes(b"not a zip")  # 깨진 zip
    seg = pd.read_csv(paths.results / "segments.csv")
    seg.loc[0, "cv_pct"] = np.nan  # 실험 1 결과의 빈칸(걸음이 모자란 곡 구간)
    seg.to_csv(paths.results / "segments.csv", index=False)
    return run_exp23(paths, params, real=False), paths


def test_messy_sheet_does_not_stop_the_run(messy):
    out, _ = messy
    assert len(out["trials"]) == 36  # 기록지 줄은 모두 남는다
    fails = {(q["walk_id"], q["check_id"]) for q in out["qa"] if q["status"] == "FAIL"}
    assert ("E2_C_100_2", "Q01") in fails  # 깨진 zip
    assert ("E2_A_165_2", "Q01") in fails and ("E2_A_165_1", "Q01") in fails  # 같은 zip
    h2 = {r["participant"] for r in out["hypotheses"] if r["hypothesis"] == "H2_variability"}
    assert h2 - {"ALL"} == {"A", "B", "C"}  # 실험 1 표의 빈칸 때문에 멈추지 않는다


def test_messy_sheet_values_kept_without_zip(messy):
    out, _ = messy
    tr = out["trials"].set_index("trial_id")
    assert tr.loc["E2_A_150_1", "gait_video"] == "run" and "no_zip" in tr.loc["E2_A_150_1", "flags"]
    assert tr.loc["E2_A_150_1", "v_ms"] > 0
    h3 = {r["participant"]: r["supported"] for r in out["hypotheses"] if r["hypothesis"] == "H3"}
    assert h3["A"] is True and h3["C"] is True  # A: zip 없는 뛴 시행, C: 한글 판정
    pcs = out["pcs"].set_index("runner")
    assert pcs.loc["B", "n_silent"] == 2 and pcs.loc["B", "pc_field_spm"] == pytest.approx(105, abs=1.0)


def test_messy_invalid_trial_excluded_from_stage(messy):
    out, _ = messy
    s = out["summary"]
    assert int(s[(s["runner"] == "B") & (s["ratio_pct"] == "120")]["n_trials"].iloc[0]) == 1
    assert "invalid_sheet" in out["trials"].set_index("trial_id").loc["E2_B_120_2", "flags"]


def test_fill_prescription_rerun_replaces_flags(messy):
    from walkmusic.exp23 import fill_prescription

    _, paths = messy
    pres = pd.read_csv(paths.results / "prescription.csv")
    pres["flags"] = ""  # 모든 칸이 빈 flags로 저장된 경우(다시 읽으면 숫자 열이 된다)
    pres.to_csv(paths.results / "prescription.csv", index=False)
    first = pd.DataFrame([dict(runner="A", t_high_pct=120.0, t_high_s3_pct=120.0,
                               flags="t_high_pct_not_broken;t_high_s3_pct_not_broken")])
    second = pd.DataFrame([dict(runner="A", t_high_pct=150.0, t_high_s3_pct=135.0, flags="")])
    fill_prescription(paths, first)
    fill_prescription(paths, second)
    a = pd.read_csv(paths.results / "prescription.csv").query("participant == 'A' and row_type == 'summary'").iloc[0]
    assert a["t_high_pct"] == 150.0
    assert "not_broken" not in str(a["flags"])


def test_jump_person_medians(res):
    out, paths, _ = res
    js = pd.read_csv(paths.results / "jumps_summary.csv").set_index("runner")
    assert set(js.index) == {"A", "B", "C"}
    a = out["jumps"][out["jumps"]["runner"] == "A"]
    assert js.loc["A", "flight_time_s"] == pytest.approx(a["flight_time_s"].median())  # SPEC §5.7: 3회 중앙값
