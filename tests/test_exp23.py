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
