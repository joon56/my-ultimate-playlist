"""민감도 분석: 기준을 한 가지씩 바꾼 결과를 기본 결과와 나란히 (SPEC §5.5d, §6, D-42)."""

import numpy as np
import pandas as pd
import pytest

from walkmusic.sensitivity import COLS, sensitivity_table, synced_walks


@pytest.fixture(scope="module")
def exp1_set(tmp_path_factory):
    """한 사람(A) 8회: 무음 2회 + 음악 6회. 케이던스가 템포를 30% 따라간다."""
    from walkmusic.config import load_params
    from walkmusic.exp1 import make_synthetic_dataset, process_all

    params = load_params()
    paths, _ = make_synthetic_dataset(tmp_path_factory.mktemp("sens"), params, people=("A",), n_walks=8, seed=21)
    segs, walks, _ = process_all(paths, params)
    shifted = {s: process_all(paths, params, offset_shift_s=s)[0] for s in (-5.0, 5.0)}
    return segs, walks, shifted


def _summary():
    """실험 2 단계 표: 100%는 박자에 맞고, 120%는 평균 케이던스가 박자보다 4% 느리다(±3% 밖, ±5% 안)."""
    return pd.DataFrame(dict(
        runner="A", ratio_pct=["S", "100", "120", "135"], bpm_played=[np.nan, 110.0, 130.0, 150.0],
        tempo_ratio_pct=[np.nan, 100.0, 118.2, 136.4], cadence_median_spm=[110.0, 110.5, 124.8, 131.0],
        cadence_rate_spm=[110.0, 110.5, 124.8, 131.0], sync3_pct=[np.nan, 85.0, 30.0, 0.0],
        sync5_pct=[np.nan, 95.0, 82.0, 5.0], mean_sync=["NA", True, False, False]))


def _rows(t, variant, hypothesis, who="A"):
    return t[(t["variant"] == variant) & (t["hypothesis"] == hypothesis) & (t["participant"] == who)]


def test_sensitivity_variants_and_columns(exp1_set, params):
    segs, walks, shifted = exp1_set
    t = sensitivity_table(segs, walks, _summary(), pd.DataFrame(), shifted, params)
    assert list(t.columns) == COLS
    assert set(t["variant"]) == {"sync_tol_5pct", "offset_minus_5s", "offset_plus_5s", "exclude_hurried",
                                 "exclude_rain", "pc_first_silent", "exclude_tried_to_sync"}
    # 합성 기록지에는 서두름·날씨·설문이 없다: 한 줄로 '기본 결과와 같다'
    for v, word in (("exclude_hurried", "서두른 회차가 없어"), ("exclude_rain", "비 온 회차가 없어"),
                    ("exclude_tried_to_sync", "종료 설문이 아직 없다")):
        d = t[t["variant"] == v]
        assert len(d) == 1 and word in d["note"].iloc[0] and not d["supported_changed"].iloc[0]
    assert "기록이 빈 회차 8개" in t.loc[t["variant"] == "exclude_rain", "note"].iloc[0]


def test_sync_tolerance_variant_changes_h12_and_upper_bound(exp1_set, params):
    segs, walks, shifted = exp1_set
    t = sensitivity_table(segs, walks, _summary(), pd.DataFrame(), shifted, params)
    h12 = _rows(t, "sync_tol_5pct", "H1-2").iloc[0]
    assert h12["supported_base"] == False  # noqa: E712  S3 30% < 80%
    assert h12["supported_variant"] == True and h12["supported_changed"]  # noqa: E712  S5 82% ≥ 80%
    assert h12["value_base"] == pytest.approx(30.0) and h12["value_variant"] == pytest.approx(82.0)
    up = _rows(t, "sync_tol_5pct", "prescription")
    hi = up[up["metric"] == "t_high_pct"].iloc[0]
    assert hi["value_base"] == pytest.approx(100.0) and hi["value_variant"] == pytest.approx(118.2)
    h1 = _rows(t, "sync_tol_5pct", "H1").iloc[0]
    assert h1["value_base"] == pytest.approx(h1["value_variant"])  # ρ는 동조 기준과 무관하다


def test_offset_and_pc_variants_recompute_exp1(exp1_set, params):
    segs, walks, shifted = exp1_set
    t = sensitivity_table(segs, walks, pd.DataFrame(), pd.DataFrame(), shifted, params)
    for v in ("offset_minus_5s", "offset_plus_5s"):
        h1 = _rows(t, v, "H1").iloc[0]
        assert h1["n_variant"] >= 12 and h1["value_variant"] > 0.5 and h1["supported_variant"] == True  # noqa: E712
        assert len(_rows(t, v, "prescription")) == 1
    pc = _rows(t, "pc_first_silent", "H1").iloc[0]
    assert pc["value_variant"] == pytest.approx(pc["value_base"])  # 순위 상관은 PC를 바꿔도 같다
    assert "걸음/분" in pc["note"]
    assert set(t.loc[t["variant"] == "sync_tol_5pct", "hypothesis"]) == {"H1"}  # 실험 2 표가 없으면 가설 1만


def test_excluding_walks_by_sheet_and_debrief(exp1_set, params):
    segs, walks, shifted = exp1_set
    walks = walks.copy()
    walks["hurried"] = walks["hurried"].astype(object)
    music = walks[walks["condition"] != "S"]
    walks.loc[music.index[0], "hurried"] = "예"
    debrief = pd.DataFrame(dict(participant=["A"], tried_to_sync=["예"],
                                sync_walks=[f"{music['walk_no'].iloc[1]}, {music['walk_no'].iloc[2]}"]))
    assert synced_walks(debrief) == {("A", int(music["walk_no"].iloc[1])), ("A", int(music["walk_no"].iloc[2]))}
    t = sensitivity_table(segs, walks, pd.DataFrame(), debrief, shifted, params)
    h = _rows(t, "exclude_hurried", "H1").iloc[0]
    assert h["n_variant"] < h["n_base"] and music["walk_id"].iloc[0] in h["note"] and "뺀 회차 1개" in h["note"]
    d = _rows(t, "exclude_tried_to_sync", "H1").iloc[0]
    assert "뺀 회차 2개" in d["note"] and d["n_variant"] < h["n_variant"]
