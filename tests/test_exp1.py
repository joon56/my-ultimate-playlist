"""실험 1 곡 구간과 지표 (SPEC §5.5–5.6, DECISIONS D-01·D-05·D-07·D-19·D-59·D-67)."""

import numpy as np
import pandas as pd
import pytest

from walkmusic.config import ROOT
from walkmusic.exp1 import interval_table, make_synthetic_dataset, process_all, segment_metrics, song_timeline
from walkmusic.qa import read_table

MUSIC = read_table(ROOT / "data" / "music_bpm.csv")


def _dur(playlist, order):
    m = MUSIC[(MUSIC["playlist"] == playlist) & (MUSIC["order"] == order)]
    return float(m["duration_s"].iloc[0])


def test_song_timeline_cycles_from_start_song():
    songs = song_timeline(dict(condition="P2", start_song="2", songs_played=""), MUSIC, offset_s=3.0, rec_end_s=700)
    assert [s.order for s in songs[:4]] == ["2", "3", "1", "2"]
    assert songs[0].t0 == 3.0 and songs[0].t1 == pytest.approx(3.0 + _dur("P2", "2"))
    assert songs[1].t0 == pytest.approx(songs[0].t1)
    assert songs[-1].t0 < 700 <= songs[-1].t1
    assert songs[0].bpm == 109.0  # Next Level


def test_song_timeline_uses_songs_played_then_continues():
    songs = song_timeline(dict(condition="P3", start_song="1", songs_played="P3-2;P3-3"), MUSIC, 3.0, 800)
    assert [s.order for s in songs[:4]] == ["2", "3", "1", "2"]


def test_song_timeline_stops_when_duration_missing():
    m = MUSIC.copy()
    m.loc[(m["playlist"] == "P1") & (m["order"] == "2"), "duration_s"] = ""
    with pytest.raises(ValueError, match="duration_s"):
        song_timeline(dict(condition="P1", start_song="1", songs_played=""), m, 3.0, 700)


def test_interval_table_edges_stops_manual_and_range(params):
    t = np.r_[np.arange(0, 50, 0.5), np.arange(53, 70.01, 0.5), 70.2, np.arange(70.7, 100.01, 0.5)]
    iv = interval_table(t, t_depart=0.0, t_arrive=100.0, params=params, manual=[(60.0, 62.0)])

    def reason_at(x):
        return iv.loc[(iv["t0"] <= x) & (iv["t1"] > x), "reason"].iloc[0]

    assert reason_at(10) == "edge" and reason_at(90) == "edge"          # 출발·도착 뒤·앞 20 s
    assert reason_at(51) == "stop"                                       # 3.5 s 정지
    assert reason_at(48.7) == "stop" and reason_at(53.6) == "stop"       # 정지 앞뒤 2 s(D-19)
    assert reason_at(70.1) == "range"                                    # 0.2 s 간격
    assert reason_at(61) == "manual"
    assert reason_at(30) == "" and bool(iv.loc[iv["t0"] == 30.0, "valid"].iloc[0])


def test_segment_metrics_sync_and_sub_super(params):
    iv = np.full(40, 0.5)  # 120 spm
    m = segment_metrics(iv, np.full(40, 1.3), 120.0, params)
    assert m["cadence_median_spm"] == pytest.approx(120) and m["sync3_pct"] == pytest.approx(100)
    assert m["sub_super"] == "none" and m["impact_g"] == pytest.approx(1.3)
    assert segment_metrics(iv, np.full(40, 1.3), 240.0, params)["sub_super"] == "sub"
    assert segment_metrics(iv, np.full(40, 1.3), 60.0, params)["sub_super"] == "super"
    few = segment_metrics(np.full(10, 0.5), np.full(10, 1.3), 120.0, params)
    assert few["flags"] == "few_steps" and np.isnan(few["cadence_median_spm"])


@pytest.fixture(scope="module")
def follow_set(tmp_path_factory):
    """한 사람: 무음 3회 + 플레이리스트 4개 × 2회. 케이던스가 템포를 30% 따라간다."""
    from walkmusic.config import load_params
    params = load_params()
    root = tmp_path_factory.mktemp("exp1_follow")
    paths, truth = make_synthetic_dataset(root, params, people=("A",), follow=0.3, seed=3)
    segs, walks, _ = process_all(paths, params)
    return paths, truth, segs, walks


def test_synthetic_song_cadence_and_speed_recovered(follow_set):
    _, truth, segs, walks = follow_set
    music = segs[(segs["condition"] != "S") & ~segs["flags"].str.contains("few_steps")]
    assert len(music) >= 20  # 걷기 끝에 조금만 걸친 곡 구간은 few_steps로 남고 지표가 비어 있다(D-08)
    for r in music.itertuples():
        want_c, want_v = truth[r.walk_id][r.song_idx]
        assert r.cadence_median_spm == pytest.approx(want_c, rel=0.01)
        assert r.speed_ms == pytest.approx(want_v, rel=0.05)
        assert r.step_length_m == pytest.approx(want_v / (want_c / 60), rel=0.06)
    silent = walks[walks["condition"] == "S"]
    assert len(silent) == 3 and silent["cadence_median_spm"].notna().all()
    assert (walks["mean_av_g"] - 1).abs().max() < 0.02  # SPEC §9 #32의 점검값: 걷는 동안 평균 1 g


def test_gps_sparse_when_location_stops_after_start(tmp_path, params):
    """B처럼 위치 점이 기록 처음 10초에만 있으면 gps_sparse이고 속도를 내지 않는다(D-67)."""
    import io

    from walkmusic.exp1 import process_walk
    from walkmusic.qa import Paths
    from walkmusic.synthetic import SynthSpec, make_files, write_zip

    files, _ = make_files(SynthSpec(walk_s=120, seed=7))
    loc = pd.read_csv(io.BytesIO(files["Location.csv"]))
    loc = loc[loc["seconds_elapsed"] < 10]
    (tmp_path / "raw" / "A").mkdir(parents=True)
    write_zip(tmp_path / "raw" / "A" / "w.zip",
              SynthSpec(walk_s=120, seed=7, extra_files={"Location.csv": loc.to_csv(index=False).encode()}))
    paths = Paths(tmp_path / "raw", tmp_path / "m.csv", ROOT / "data" / "assignment.csv", tmp_path / "mu.csv",
                  tmp_path / "p.csv", tmp_path / "s.csv", tmp_path / "out")
    row = dict(walk_id="E1_A_01_S_1110", participant="A", condition="S", zip_file="w.zip")
    segs, walk, _ = process_walk(row, paths, params, MUSIC, pd.DataFrame())
    assert "gps_sparse" in walk["flags"] and np.isnan(walk["speed_ms"])
    assert "gps_sparse" in segs[0]["flags"]


def test_no_coordinates_in_outputs(follow_set):
    _, _, segs, walks = follow_set
    for df in (segs, walks):
        assert not any(c.lower() in ("lat", "lon", "latitude", "longitude") for c in df.columns)
