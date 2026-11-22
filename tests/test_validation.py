"""측정 검증표와 그 입력(몸 중심 수직 변위, 역진자 보폭, 측정 구간 통과) (SPEC §4.3, §5.5e, §5.10, D-38·D-40)."""

import numpy as np
import pytest

from walkmusic import metrics as m


def test_com_vertical_displacement_recovers_sine_amplitude(params):
    g = params["constants.g"]
    h, period = 0.040, 0.55  # 한 걸음 동안 몸 중심이 4 cm 오르내린다
    t = np.arange(0, period + 1e-9, 0.01)
    accel = -(h / 2) * (2 * np.pi / period) ** 2 * np.cos(2 * np.pi * t / period)  # z = (h/2) cos(2πt/T)의 두 번 미분
    got = m.com_vertical_displacement_m(t, 1.0 + accel / g, g)
    assert got == pytest.approx(h, rel=0.02)
    # 센서가 한쪽으로 치우쳐도(평균 1.03 g) 걸음 안 평균을 빼므로 같다
    assert m.com_vertical_displacement_m(t, 1.03 + accel / g, g) == pytest.approx(h, rel=0.02)
    assert np.isnan(m.com_vertical_displacement_m(t[:2], np.ones(2), g))


@pytest.fixture(scope="module")
def small_exp1(tmp_path_factory):
    """한 사람(A) 무음 1회 + 음악 2회. 다리 길이는 실제 participants.csv의 A 값."""
    from walkmusic.config import load_params
    from walkmusic.exp1 import make_synthetic_dataset, process_all

    params = load_params()
    paths, _ = make_synthetic_dataset(tmp_path_factory.mktemp("val_exp1"), params, people=("A",), n_walks=3, seed=11)
    segs, walks, _ = process_all(paths, params)
    return paths, segs, walks


def test_segments_and_walks_have_com_and_zh_step_length(small_exp1, params):
    from walkmusic.qa import read_table

    paths, segs, walks = small_exp1
    leg = float(read_table(paths.participants).set_index("participant").loc["A", "leg_length_m"])
    for df in (segs[~segs["flags"].str.contains("few_steps")], walks):
        h = df["com_vertical_m"].to_numpy(float)
        assert np.isfinite(h).all() and (h > 0.001).all() and (h < 0.15).all()
        want = [m.step_length_zh(leg, x, params["com.zh_correction"]) for x in h]
        assert df["step_length_zh_m"].to_numpy(float) == pytest.approx(want)
    few = segs[segs["flags"].str.contains("few_steps")]
    assert few["com_vertical_m"].isna().all()  # 걸음이 모자란 구간은 내지 않는다(D-08)


def test_section_speed_from_waypoints(tmp_path, params):
    """웨이포인트 두 점(출발에서 40 m, 120 m) 사이를 1.3 m/s로 지난다: 지도 거리 80 m ÷ 통과 시간."""
    import pandas as pd

    from walkmusic.config import ROOT
    from walkmusic.exp1 import process_walk
    from walkmusic.qa import Paths, read_table
    from walkmusic.synthetic import SynthSpec, write_zip

    (tmp_path / "raw" / "A").mkdir(parents=True)
    write_zip(tmp_path / "raw" / "A" / "w.zip", SynthSpec(walk_s=150, speed_mps=1.3, seed=4))
    paths = Paths(tmp_path / "raw", tmp_path / "m.csv", ROOT / "data" / "assignment.csv", tmp_path / "mu.csv",
                  tmp_path / "p.csv", tmp_path / "s.csv", tmp_path / "out")
    deg = np.degrees(1.0 / 6371008.8)  # 1 m의 위도
    way = pd.DataFrame(dict(participant="A", seq=["1", "2"], lat=[0.001 + 40 * deg, 0.001 + 120 * deg],
                            lon=[0.001, 0.001]))
    row = dict(walk_id="E1_A_01_S_1110", participant="A", condition="S", zip_file="w.zip")
    music = read_table(ROOT / "data" / "music_bpm.csv")
    person = dict(leg_length_m=0.9, section_distance_m=80.0, waypoints=way)
    _, walk, _ = process_walk(row, paths, params, music, pd.DataFrame(), person)
    assert walk["section_time_s"] == pytest.approx(80 / 1.3, abs=2.0)
    assert walk["speed_section_ms"] == pytest.approx(1.3, rel=0.04)
    assert walk["section_gps_m"] == pytest.approx(80.0, rel=0.06)
    assert walk["speed_doppler_section_ms"] != walk["speed_doppler_section_ms"]  # 합성 Doppler 정확도 0.9 > 0.5: 없음
    assert not any(k.lower() in ("lat", "lon", "latitude", "longitude") for k in walk)
    # 웨이포인트가 없거나 반경 밖이면 비운다
    _, none, _ = process_walk(row, paths, params, music, pd.DataFrame(), dict(section_distance_m=80.0))
    far = way.assign(lat=[0.5, 0.6])
    _, off, _ = process_walk(row, paths, params, music, pd.DataFrame(), dict(section_distance_m=80.0, waypoints=far))
    assert np.isnan(none["speed_section_ms"]) and np.isnan(off["speed_section_ms"])


def test_offset_shift_moves_song_windows(small_exp1, params):
    from walkmusic.exp1 import process_all

    paths, segs, _ = small_exp1
    shifted, _, _ = process_all(paths, params, offset_shift_s=5.0)
    key = ["walk_id", "song_idx"]
    both = segs[segs["song_idx"] == 1].merge(shifted[shifted["song_idx"] == 1], on=key, suffixes=("", "_shift"))
    # 두 번째 곡은 유효 창 안에서 시작한다: 곡 구간의 시작이 5 s 밀린다
    assert len(both) == 2
    assert (both["seg_t0_s_shift"] - both["seg_t0_s"]).to_numpy() == pytest.approx(5.0)
    silent = shifted[shifted["condition"] == "S"]
    assert silent["seg_t0_s"].iloc[0] == segs.loc[segs["condition"] == "S", "seg_t0_s"].iloc[0]  # 무음은 그대로


def _tables():
    import pandas as pd

    trials = pd.DataFrame(dict(
        trial_id=[f"E2_A_{k}" for k in range(4)] + ["E2_B_0", "E2_B_1", "E2_B_x"], runner=list("AAAABBB"),
        cadence_record_spm=[110, 112, 115, 120, 100, 104, 150], cadence_median_spm=[111, 112, 113, 121, 101, 103, 100],
        contact_time_s=np.nan, flight_time_median_s=np.nan, flags=["", "", "", "", "", "", "invalid_sheet"]))
    jumps = pd.DataFrame(dict(
        runner=list("AAABB"), flight_time_s=[0.50, 0.52, 0.56, 0.53, 0.50],
        flight_time_video_s=[np.nan, np.nan, 0.51, 0.50, 0.51], takeoff_v_flight_ms=[2.45, 2.55, 2.75, 2.60, 2.45],
        takeoff_v_int_ms=[2.10, 2.20, 2.30, 2.25, 2.15], flags=["", "", "invalid_sheet", "", ""]))
    swings = pd.DataFrame(dict(
        runner=list("BAABB"), knee=["bent", "straight", "bent", "straight", "bent"],
        swing_period_s=[2.0, 1.51, 1.41, 1.44, 1.60], video_period_s=[1.0, 1.50, 1.42, 1.45, 1.58],
        flags=["no_swing", "", "", "", "few_cycles;invalid_sheet"]))  # 첫 줄은 흔들림을 못 찾은 시행: 뺀다
    segments = pd.DataFrame(dict(
        participant=list("AAAB"), step_length_zh_m=[0.60, 0.66, 0.63, 0.5], step_length_m=[0.75, 0.75, 0.70, np.nan],
        flags=["", "", "gps_sparse", "gps_sparse"]))
    walks = pd.DataFrame(dict(
        participant=list("AAB"), mean_av_g=[1.006, 1.002, 1.000], section_gps_m=[270.0, 272.0, np.nan],
        section_time_s=[200.0, 204.0, np.nan], speed_section_ms=[1.326, 1.300, np.nan],
        speed_doppler_section_ms=[1.25, 1.31, np.nan]))
    checks = pd.DataFrame(dict(trial_id=["E2_A_0", "E2_A_0", "E2_B_0"], kind=["run_contact"] * 3,
                               value_s=["0.254", "0.241", "0.275"]))
    hand = pd.DataFrame(dict(participant=["A"], walk_id=["T"], detected=[102], hand=[100.0]))
    return trials, jumps, swings, segments, walks, checks, hand


def test_validation_table_rows_and_bland_altman(params):
    from walkmusic.validation import COLS, validation_table

    v = validation_table(*_tables(), params, fps=dict(exp2=59.94, jump=240, swing=60, run=240))
    assert list(v.columns) == COLS

    def row(measure, who):
        return v[(v["measure"] == measure) & (v["participant"] == who)].iloc[0]

    a = row("exp2_cadence", "A")  # SPEC §9 #30의 숫자
    assert a["n"] == 4 and a["bias"] == pytest.approx(0.0) and a["mean_abs_diff"] == pytest.approx(1.0)
    assert a["loa_high"] == pytest.approx(1.96 * np.std([-1, 0, 2, -1], ddof=1))
    assert row("exp2_cadence", "B")["n"] == 2  # valid=0 줄은 뺀다
    assert row("exp2_cadence", "ALL")["n"] == 6 and "독립이 아니다" in row("exp2_cadence", "ALL")["note"]
    assert "1/59.94 s" in a["resolution"]

    assert row("jump_flight", "A")["n"] == 1 and row("jump_flight", "ALL")["n"] == 3  # 검증용 기록의 점프도 쓴다
    assert "valid=0" in row("jump_flight", "ALL")["note"] and "valid=0" not in row("jump_flight", "B")["note"]
    assert row("jump_flight", "ALL")["bias"] == pytest.approx(np.mean([0.05, 0.03, -0.01]))
    assert row("jump_takeoff_velocity", "A")["n"] == 2  # 사람 값에서 뺀 기록은 넣지 않는다(D-87)

    sw = row("swing_period", "ALL")
    assert sw["n"] == 4 and "곧은 다리 2개·굽힌 다리 2개" in sw["note"] and "valid=0 시행 1개" in sw["note"]
    assert "곧은 다리 1개·굽힌 다리 1개" in row("swing_period", "A")["note"]
    assert "1.7 ms" in sw["resolution"]

    sl = v[v["measure"] == "step_length"]
    assert list(sl["participant"]) == ["A"] and sl["n"].iloc[0] == 2  # 위치가 드문 구간은 뺀다(D-67)
    assert "SL_ZH ÷ SL 평균 0.84" in sl["note"].iloc[0]

    rc = v[v["measure"] == "run_contact_time"]
    assert list(rc["participant"]) == ["ALL"] and rc["n"].iloc[0] == 0 and "영상 판독 3개" in rc["note"].iloc[0]

    av = row("mean_vertical_accel", "A")
    assert av["bias"] == pytest.approx(0.004) and np.isnan(av["loa_low"]) and "범위 1.002–1.006 g" in av["note"]
    assert row("steps_100", "A")["bias"] == pytest.approx(2.0)
    d = row("section_distance", "A")
    assert d["mean_b"] == pytest.approx(265.2, abs=0.01) and d["bias"] == pytest.approx(5.8, abs=0.01)
    assert row("section_speed_doppler", "A")["n"] == 2
    assert not any(c.lower() in ("lat", "lon", "latitude", "longitude") for c in v.columns)


def test_validation_table_with_empty_inputs(params):
    import pandas as pd

    from walkmusic.validation import validation_table

    e = pd.DataFrame()
    v = validation_table(e, e, e, e, e, e, e, params)
    assert (v["n"] == 0).all() and set(v["participant"]) == {"ALL"} and v["measure"].nunique() == len(v) == 11
