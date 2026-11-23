"""손계산 검산 도구(tools/handcalc_check.py).

식 함수가 손계산 노트(HANDCALC)의 예시·패키지 함수와 같은 답을 내는지, 교안 예제 50개 풀이가 검산 기준값과 같은지,
같은 입력이면 같은 표가 나오는지 본다. 실제 결과 표가 있을 때만 도는 테스트는 따로 표시했다.
"""

import importlib.util
import sys

import numpy as np
import pytest
from scipy import stats

from walkmusic import metrics as m
from walkmusic.config import ROOT, load_params

_spec = importlib.util.spec_from_file_location("handcalc_check", ROOT / "tools" / "handcalc_check.py")
hc = importlib.util.module_from_spec(_spec)
sys.modules["handcalc_check"] = hc
_spec.loader.exec_module(hc)

P = load_params()
G = 9.81
SEG = {k: P[f"pendulum.seg_{k}_frac"] for k in ("thigh_mass", "thigh_com", "thigh_kcm", "shank_mass", "shank_com",
                                                "shank_kcm")}
RAW = ROOT / "data" / "raw"
HAS_RESULTS = all((ROOT / "results" / f).exists() for f in ("segments.csv", "exp2_summary.csv", "exp3_swings.csv",
                                                           "jumps.csv", "validation.csv"))
HAS_RAW = HAS_RESULTS and RAW.exists() and any(RAW.rglob("*.zip"))


def test_rank_average_gives_mean_rank_to_ties():
    assert hc.rank_average([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]
    assert hc.rank_average([3, 1, 2]) == [3.0, 1.0, 2.0]


def test_spearman_by_hand_equals_scipy():
    x = [102.9, 110.3, 110.3, 119.7, 131.4, 95.0, 102.9, 125.0]
    y = [2.0, 7.1, 6.5, 7.9, 7.8, -1.0, 2.5, 7.9]
    assert hc.spearman(x, y) == pytest.approx(stats.spearmanr(x, y).statistic, abs=1e-12)
    a, b = [1, 2, 3, 4, 5], [2, 1, 4, 3, 5]  # 같은 값이 없으면 1 − 6Σd² ÷ (n(n² − 1))과 같다
    rho, d2 = hc.spearman_no_ties(a, b)
    assert d2 == 4
    assert rho == pytest.approx(0.8)
    assert hc.spearman(a, b) == pytest.approx(0.8)
    assert list(hc.rank_table(a, b)["d"]) == [-1.0, 1.0, -1.0, 1.0, 0.0]


def test_bland_altman_equals_package():
    a, b = [110, 112, 115, 120], [111, 112, 113, 121]  # SPEC §9 #30
    r, code = hc.bland_altman(a, b), m.bland_altman(a, b, P["stats.sd_ddof"])
    assert (r.n, r.mean, r.sd, r.low, r.high) == pytest.approx(
        (code["n"], code["bias"], code["sd"], code["loa_low"], code["loa_high"]))
    assert r.sd == pytest.approx(1.414, abs=5e-4)
    assert r.mean_b == pytest.approx(code["mean_b"])


def test_segment_model_equals_note_and_package():
    fr = hc._fractions(P)
    for knee, inertia, d, period in ((0.0, 2.057, 0.366, 1.531), (90.0, 1.284, 0.286, 1.367)):  # HANDCALC 7번
        s = hc.segment_model(60, 0.4165, 0.4182, knee, fr)
        code = m.segment_pendulum(60, 0.4165, 0.4182, knee, G, SEG)
        assert (s.I, s.d, s.P) == pytest.approx((inertia, d, period), abs=5e-4)
        assert (s.m, s.I, s.d, s.P) == pytest.approx(
            (code["mass_kg"], code["inertia_hip_kgm2"], code["com_dist_m"], code["period_s"]))
    model = hc.whole_leg_period(0.90, P["pendulum.k_over_L"], P["pendulum.d_over_L"])
    assert model == pytest.approx(1.594, abs=5e-4)
    assert model == pytest.approx(m.pendulum_period_model_s(0.90, P["pendulum.k_over_L"], P["pendulum.d_over_L"], G))


def test_knee_angles_equal_note_and_lecture_example():
    inner, flex = hc.knee_cosine((0, 0), (50, 420), (-100, 800))  # HANDCALC 10번
    assert (inner, flex) == pytest.approx((151.67, 28.33), abs=5e-3)
    assert flex == pytest.approx(m.knee_angles((0, 0), (50, 420), (-100, 800))["knee_flexion_deg"])
    hip, knee, ankle = (1.14, 0.80), (1.22, 0.51), (1.09, 0.09)  # 교안 11주차 p28 예제 1의 세 점
    thigh, shank = hc.absolute_angles(hip, knee, ankle)
    assert (thigh, shank) == pytest.approx((105.4, 72.8), abs=0.05)
    assert thigh - shank == pytest.approx(hc.knee_cosine(hip, knee, ankle)[1])
    flipped = [(x, -y) for x, y in (hip, knee, ankle)]  # 영상 좌표(y가 아래로 커짐)는 뒤집어 같은 각을 낸다
    assert hc.absolute_angles(*flipped, image_y_down=True) == pytest.approx((thigh, shank))


def test_spring_equals_note_and_package():
    s, code = hc.spring(60, 0.90, 3.0, 0.25, 0.10), m.spring_mass(60, 0.25, 0.10, 3.0, 0.90, G)  # HANDCALC 6번
    assert (s.fmax, s.bw, s.dy, s.dl, s.kvert, s.kleg, s.energy) == pytest.approx(
        (code["fmax_n"], code["fmax_bw"], code["delta_y_m"], code["delta_l_m"], code["kvert_kn_m"], code["kleg_kn_m"],
         code["elastic_energy_j"]))
    assert (s.fmax, s.kvert, s.energy) == pytest.approx((1294.4, 21.58, 38.8), abs=0.05)


def test_sync_count_counts_intervals_inside_band():
    t = list(np.arange(11) * 60 / 105)  # 간격 10개가 105 걸음/분
    t += [t[-1] + 0.50, t[-1] + 1.00, t[-1] + 3.00]  # 120 걸음/분 간격 2개(±3% 밖), 2 s 간격 1개(유효 범위 밖)
    n_steps, n_valid, n_in, s3 = hc.sync_count(t, 0.0, 100.0, 105, 3.0, 0.23, 1.50)
    assert (n_steps, n_valid, n_in) == (14, 12, 10)
    assert s3 == pytest.approx(10 / 12 * 100)
    code = m.sync_counts([60 / d for d in np.diff(t) if 0.23 <= d <= 1.50], 105, 3.0)
    assert s3 == pytest.approx(code["sync_pct"])
    assert hc.sync_count(t, 0.0, t[10], 105, 3.0, 0.23, 1.50)[:3] == (11, 10, 10)  # 창 밖 걸음은 세지 않는다


def test_interval_cv_is_sample_sd_over_mean():
    iv = [0.50, 0.52, 0.48, 0.50]
    assert hc.interval_cv(iv) == pytest.approx(3.266, abs=5e-4)
    assert hc.interval_cv(iv) == pytest.approx(m.cv_pct(iv, P["stats.sd_ddof"]))


def test_reference_text_helpers():
    assert hc.same_as_ref(1741.75, "1,741.8")
    assert hc.same_as_ref(-8.886, "−8.89")
    assert not hc.same_as_ref(0.7478, "0.750")
    assert hc.show(99.7189, "99.72") == "99.72"  # 같으면 기준값 글자 그대로
    assert hc.show(0.7477609, "0.750") == "0.748"  # 다르면 같은 자릿수로 원값
    assert hc.show(0.4355718, "+0.48") == "+0.44"
    assert hc.show(-4.27647, "−4.24") == "−4.28"
    assert hc.show(1203.2117, "1,202.9") == "1,203.2"
    assert hc.show(-0.00004, nd=2) == "0.00"
    assert hc.show(1181.4, nd=0) == "1,181"


def test_sheet_compares_hand_code_and_reference():
    sh = hc.Sheet()
    sh.begin("HC-X", "결론", "교안", "실측", "식", "입력")
    sh.add("같은 값", 1.0, 1.0 + 1e-12, "1.00")
    sh.add("다른 값", 1.0, 1.1, "1.2")
    sh.add("읽은 값", None, 2.345, "2.35")
    sh.add("값 없음", float("nan"))
    a, b, c, d = sh.rows
    assert (a.match, a.ref_match) == ("일치", "같음")
    assert (b.match, b.ref_match) == ("불일치", "다름")
    assert (c.match, c.ref_match, c.value) == ("", "같음", 2.345)
    assert (d.hand, d.match, d.ref_match, d.shown) == (None, "", "", "")
    assert a.cells()[:5] == ["HC-X", "결론", "교안", "입력", "식"]
    assert len(a.cells()) == len(hc.COLUMNS)
    assert sh.get("HC-X", "다른 값") is b
    assert sh.of("HC-X") == sh.rows
    with pytest.raises(AssertionError):
        sh.begin("HC-Y", "없는 구분")


def test_lecture_examples_are_fifty_and_match_reference_values():
    ex = hc.lecture_examples()
    assert [e.no for e in ex] == list(range(1, 51))
    values = [(e.no, item, value, ref) for e in ex for item, _, value, ref in e.values]
    assert len(values) == 108
    assert [v for v in values if not hc.same_as_ref(v[2], v[3])] == []
    assert sum("예제" in e.cite for e in ex) == 47  # 번호 붙은 예제 47 + 7주차 두 문제 + 11주차 보행 분석 표
    assert [e.no for e in ex if e.figure] == [5, 50]  # 교안 그림에서 값을 읽은 것
    assert [e.no for e in ex if not e.values] == [47]  # 말로 답하는 예제
    by = {e.no: e for e in ex}
    text = by[21].answer.format(*[hc.show(v, r) for _, _, v, r in by[21].values])
    assert text == ("수평 100 cos 45° = 70.71 N, 수직력 98.1 + 100 sin 45° = 168.81 N, "
                    "최대 마찰력 0.68 × 168.81 = 114.79 N > 70.71 N → 움직이지 않음")


@pytest.mark.skipif(not HAS_RESULTS, reason="results/ 표가 없다(실제 데이터로 파이프라인을 돌린 뒤에만 돈다)")
def test_real_tables_hand_equals_code_and_output_is_reproducible(tmp_path):
    one, two = hc.build_sheet(hc.load_tables(), P), hc.build_sheet(hc.load_tables(), P)
    assert [r.cells() for r in one.rows] == [r.cells() for r in two.rows]
    assert [f"{r.id} | {r.item}" for r in one.rows if r.match == "불일치"] == []
    assert sum(r.match == "일치" for r in one.rows) >= 290
    ids = {r.id for r in one.rows}
    assert {f"HC-A{k}" for k in range(1, 15)} - ids == {"HC-A6"}  # 걸음 시각(zip)을 주지 않으면 HC-A6만 빠진다
    assert {f"HC-B{k}" for k in range(1, 21)} <= ids
    assert {f"E{k}" for k in range(1, 51)} <= ids
    assert {f"G-{k}" for k in range(1, 19)} <= ids
    assert {r.kind for r in one.rows} == set(hc.KINDS)
    assert all(r.status for r in one.rows)
    assert all(r.status.startswith("가정 예시") for r in one.rows if r.kind == "가정 예시")
    hc.write_csv(one, tmp_path / "a.csv")
    hc.write_csv(two, tmp_path / "b.csv")
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()
    head = (tmp_path / "a.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert head.split(",") == hc.COLUMNS


@pytest.mark.skipif(not HAS_RAW, reason="원자료 zip이 없다")
def test_real_step_times_reproduce_sync3_and_interval_cv():
    t = hc.load_tables()
    trials = hc.step_trials(t, P)
    assert {"E2_A_100_1", "E2_A_100_2"} <= set(trials)
    sh = hc.build_sheet(t, P, hc.detect_exp2_steps(trials))
    rows = sh.of("HC-A6")
    assert len(rows) == 9
    assert all(r.match == "일치" for r in rows if r.code is not None)
    assert sh.get("HC-A6", "A 100% 단계 S3 (%)").ref_match == "같음"
    cv = [r for r in sh.of("HC-A7") if r.item.endswith("걸음 간격 CV (%)")]  # 시행마다와 단계마다
    assert len(cv) == len(trials) + len(hc.variability_pairs(t, P))
    assert all(r.match == "일치" for r in cv)
    assert [r.id for r in sh.rows if r.match == "불일치"] == []
