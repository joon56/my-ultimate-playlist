"""핵심 그림 4장: 그려진 값, 파일, 영어 라벨, 합성 표시, 분석 고정 (SPEC §6, §8, D-18·D-35)."""

import json
import re

import numpy as np
import pandas as pd
import pytest
from matplotlib.image import imread
from matplotlib.text import Text

from walkmusic.figures import (
    FILES,
    FigureData,
    fig2_tempo_map,
    fig6_speed_flight,
    fig7_pendulum,
    first_run_t,
    make_figures,
    music_segments,
    render_all,
    stages,
)
from walkmusic.stats import FreezeError


def _data(**kw) -> FigureData:
    segments = pd.DataFrame(dict(
        participant=["A"] * 5 + ["C"] * 2, condition=["S", "P1", "P1", "P2", "P2", "P1", "S"],
        playlist=["", "P1", "P1", "P2", "P2", "P1", ""],
        tempo_ratio_pct=[np.nan, 100.0, 104.0, 118.0, 120.0, 90.0, np.nan],
        dC_pct=[0.2, 1.0, 3.0, 8.0, np.nan, -2.0, 0.0], sync3_pct=[np.nan, 60.0, 50.0, 10.0, np.nan, 5.0, np.nan]))
    base = pd.DataFrame(dict(participant=["A", "C"], pc_spm=[100.0, 118.0], sesoi_pct=[1.0, 1.5]))
    pres = pd.DataFrame(dict(participant=["A", "C"], row_type="summary", t_low_pct=[103.0, np.nan],
                             t_high_pct=[104.5, np.nan]))
    summary = pd.DataFrame(dict(
        runner="A", ratio_pct=["S", "150", "100", "165", "180"], tempo_ratio_pct=[np.nan, 150.0, 104.0, 168.0, 184.0],
        dC_pct=[-1.0, 40.0, 4.5, 66.0, 64.0], sync3_pct=[np.nan, 6.0, 69.0, 47.0, 5.0],
        v_ms=[1.26, 1.98, 1.33, 2.82, 3.42],
        fr=[0.162, 0.400, 0.180, 0.811, 1.192], gait_video=["walk", "walk", "walk", np.nan, "run"],
        flight_time_median_s=[np.nan, np.nan, np.nan, np.nan, 0.115], phase_source=[np.nan] * 4 + ["video"],
        flight_step_frac=[0.0, 0.0, 0.0, 0.016, 0.017]))
    pend = pd.DataFrame(dict(runner=["A"], period_model_s=[1.68], cadence_pend_spm=[78.4],
                             period_model_seg_bent_s=[1.529], cadence_pend_bent_spm=[84.1], knee_deg=[72.6]))
    field = pd.DataFrame(dict(runner=["A"], pc_field_spm=[100.7]))
    return FigureData(segments, base, pres, summary, pend, field, **kw)


def test_data_helpers_pick_the_rows_that_are_drawn():
    d = _data()
    seg = music_segments(d, "A")
    assert list(seg["tempo_ratio_pct"]) == [100.0, 104.0, 118.0]  # 무음과 값이 없는 구간은 그리지 않는다
    st = stages(d, "A")
    assert list(st["ratio_pct"]) == ["100", "150", "165", "180"] and list(st["gait"]) == ["walk", "walk", "", "run"]
    assert first_run_t(st) == 184.0 and np.isnan(first_run_t(stages(d, "C")))
    assert d.people() == ["A", "C"]


def test_figure_summaries_hold_the_drawn_values(params):
    d = _data()
    _, s2 = fig2_tempo_map(d)
    assert s2["A"]["segments_cadence_pct"] == [101.0, 103.0, 108.0] and s2["A"]["stages_cadence_pct"][0] == 104.5
    assert s2["A"]["pendulum_pct"]["pend_straight"] == pytest.approx(78.4) and s2["A"]["first_run_t_pct"] == 184.0
    assert s2["A"]["prescription_t_pct"] == [103.0, 104.5] and s2["C"]["n_segments"] == 1
    _, s6 = fig6_speed_flight(d, params)
    a = s6["panels"]["A"]
    assert list(s6["panels"]) == ["A"] and a["leg_length_m"] == pytest.approx(1.0, abs=0.01)  # Fr = v² ÷ (g L)에서
    assert a["speed_at_fr_limit_ms"] == pytest.approx((0.5 * 9.81 * a["leg_length_m"]) ** 0.5)
    assert a["flight_source"][-1] == "video" and a["flight_time_s"][-1] == 0.115
    _, s7 = fig7_pendulum(d)
    bars = s7["panels"]["A"]["bars_spm"]
    assert bars["straight_model"] == pytest.approx(120 / 1.68) and bars["bent_measured"] == 84.1


def test_render_all_writes_png_and_json_with_synthetic_mark(tmp_path, params):
    d = _data(synthetic=True)
    done = render_all(d, tmp_path, params)
    assert set(done) == set(FILES)
    for name in FILES.values():
        w_in = imread(tmp_path / f"{name}.png").shape[1] / 300
        assert 6.5 <= w_in <= 8.0  # 300 dpi, 폭 6.5–8 inch
        info = json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
        assert info["synthetic"] is True and len(info["params_sha256"]) == 64 and info["values"]
        assert not re.search(r"latitude|longitude|\"lat\"|\"lon\"", json.dumps(info))
    fig, _ = fig7_pendulum(d)
    assert any(t.get_text() == "SYNTHETIC" for t in fig.texts)
    fig, _ = fig7_pendulum(_data())
    assert not any(t.get_text() == "SYNTHETIC" for t in fig.texts)


def test_english_labels_when_no_korean_font(params):
    d = _data(korean=False)
    for fig in (fig2_tempo_map(d)[0], fig6_speed_flight(d, params)[0], fig7_pendulum(d)[0]):
        fig.canvas.draw()
        words = [t.get_text() for t in fig.findobj(Text)]
        assert words and not any(re.search("[가-힣]", w) for w in words)


def test_real_figures_need_the_freeze_tag(tmp_path, params):
    with pytest.raises(FreezeError):
        make_figures(tmp_path, tmp_path, tmp_path / "fig", params.with_overrides({"freeze.tag": "no-such-tag"}),
                     real=True)
    done = make_figures(tmp_path, tmp_path, tmp_path / "fig", params, real=False)  # 표가 없어도 빈 그림으로 끝난다
    assert set(done) == set(FILES)
