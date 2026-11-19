"""평소 케이던스·SESOI·가설 판정·재표집·처방 범위·분석 고정 (SPEC §4.5, §6, §9 #2·3·13·18–20·33)."""

import numpy as np
import pandas as pd
import pytest

from walkmusic.exp1 import make_synthetic_dataset, process_all
from walkmusic.stats import (
    FreezeError,
    add_tempo_columns,
    bootstrap_ci,
    h1_rows,
    person_baseline,
    prescription_rows,
    require_freeze,
)


def _walks(p, cs, cond="S"):
    return pd.DataFrame(dict(participant=p, condition=cond, status="", cadence_median_spm=cs, impact_g=1.3,
                             walk_id=[f"{p}{i}" for i in range(len(cs))]))


def test_person_baseline_examples_13_and_18(params):
    w = pd.concat([_walks("A", [108, 110, 112]), _walks("B", [110.0, 110.5, 110.2]), _walks("C", [104.0])])
    b = person_baseline(w, params).set_index("participant")
    assert b.loc["A", "pc_spm"] == pytest.approx(110) and b.loc["A", "silent_cv_pct"] == pytest.approx(1.818, abs=1e-3)
    assert b.loc["A", "sesoi_pct"] == pytest.approx(1.818, abs=1e-3) and not b.loc["A", "pc_provisional"]
    assert b.loc["B", "sesoi_pct"] == pytest.approx(1.0)  # 0.228% < 하한 1%
    assert b.loc["C", "n_silent"] == 1 and b.loc["C", "pc_provisional"] and np.isnan(b.loc["C", "silent_cv_pct"])
    assert b.loc["C", "sesoi_pct"] == pytest.approx(1.0) and "sesoi_floor_only" in b.loc["C", "flags"]  # D-69


def test_add_tempo_columns_examples_2_and_3(params):
    seg = pd.DataFrame(dict(participant=["A"], condition=["P2"], bpm=[120.0], cadence_median_spm=[115.0],
                            cadence_rate_spm=[115.0], impact_g=[1.4]))
    base = pd.DataFrame(dict(participant=["A"], pc_spm=[110.0], pc_provisional=[False], sesoi_pct=[1.818],
                             silent_impact_g=[1.3]))
    out = add_tempo_columns(seg, base, params).iloc[0]
    assert out["tempo_ratio_pct"] == pytest.approx(109.09, abs=0.005)
    assert out["dC_pct"] == pytest.approx(4.545, abs=5e-4) and out["R"] == pytest.approx(0.5)
    assert out["change_class"] == "meaningful_up" and out["impact_rel_pct"] == pytest.approx(7.692, abs=1e-3)


@pytest.fixture(scope="module")
def two_sets(tmp_path_factory):
    from walkmusic.config import load_params
    params = load_params()
    out = {}
    for follow in (0.3, 0.0):
        paths, _ = make_synthetic_dataset(tmp_path_factory.mktemp(f"f{follow}"), params, people=("A",),
                                          follow=follow, seed=5)
        segs, walks, _ = process_all(paths, params)
        base = person_baseline(walks, params)
        out[follow] = (add_tempo_columns(segs, base, params), base)
    return out


def _verdict(rows):
    return [r for r in rows if r["participant"] == "A"][0]


def test_h1_supported_when_steps_follow_tempo(two_sets, params):
    segs, base = two_sets[0.3]
    r = _verdict(h1_rows(segs, base, params))
    assert r["supported"] is True and r["value"] > 0.5 and r["ci_low"] < r["value"] < r["ci_high"]


def test_h1_not_supported_without_following(two_sets, params):
    segs, base = two_sets[0.0]
    assert _verdict(h1_rows(segs, base, params))["supported"] is not True


def test_h1_small_sample_is_na(two_sets, params):
    segs, base = two_sets[0.3]
    two_music = segs.loc[segs["condition"] != "S", "walk_id"].unique()[:2]  # 곡 구간 약 6개 < 8
    few = segs[(segs["condition"] == "S") | segs["walk_id"].isin(two_music)]
    r = _verdict(h1_rows(few, base, params))
    assert r["supported"] == "NA" and "표본 부족" in r["note"]


def test_bootstrap_reproducible_and_na_with_one_music_walk(two_sets, params):  # §9 #33
    segs, base = two_sets[0.3]
    music = segs[(segs["participant"] == "A") & (segs["condition"] != "S")]
    assert bootstrap_ci(music, params) == bootstrap_ci(music, params)
    one = music[music["walk_id"] == music["walk_id"].iloc[0]]
    assert all(np.isnan(x) for x in bootstrap_ci(one, params)["rho"])


def test_prescription_lower_bound_examples_19_and_20(params):
    pl = pd.DataFrame(dict(playlist=["P1", "P2", "P3", "P4"], t=[92.7, 100.9, 108.2, 119.1], dc=[0.4, 1.1, 2.5, 4.2]))
    rows = prescription_rows("A", pl, pc=110.0, sesoi=1.818, params=params)
    s = [r for r in rows if r["row_type"] == "summary"][0]
    assert s["t_low_pct"] == pytest.approx(108.2) and s["bpm_low"] == pytest.approx(119.0, abs=0.05)
    pl.loc[2:3, "dc"] = [1.5, 1.7]
    s = [r for r in prescription_rows("A", pl, 110.0, 1.818, params) if r["row_type"] == "summary"][0]
    assert np.isnan(s["t_low_pct"]) and "듣기만으로는 걸음이 바뀌지 않고" in s["statement"]


def test_freeze_guard(params):
    with pytest.raises(FreezeError):
        require_freeze(real=True, allow_unfrozen=False, tag="no-such-tag-for-test")
    st = require_freeze(real=True, allow_unfrozen=True, tag="no-such-tag-for-test")
    assert st["unfrozen"] is True
    assert require_freeze(real=False, allow_unfrozen=False, tag="no-such-tag-for-test")["synthetic"] is True
