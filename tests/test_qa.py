"""QA Q01–Q15와 관문 G1: 검사마다 PASS 사례와 아닌 사례(합성), 실제 파일 요약."""

import io

import numpy as np
import pandas as pd

from conftest import PRECHECK, TRIAL, real
from walkmusic.config import ROOT
from walkmusic.qa import R_EARTH, Paths, gate_g1, make_synthetic_dataset, read_table, run_checks
from walkmusic.synthetic import SynthSpec, make_files, write_zip

COLS = read_table(ROOT / "data" / "manifest.csv").columns.tolist()


def _env(tmp_path, walks, distance="200", music_duration="180"):
    """walks: [(manifest 줄 dict, SynthSpec)] → 임시 Paths."""
    paths = Paths(tmp_path / "raw", tmp_path / "manifest.csv", ROOT / "data" / "assignment.csv",
                  tmp_path / "music.csv", tmp_path / "participants.csv", tmp_path / "sections.csv", tmp_path / "out")
    paths.raw.mkdir()
    rows = []
    for row, spec in walks:
        write_zip(paths.raw / f"{row['walk_id']}.zip", spec)
        rows.append({**row, "zip_file": f"{row['walk_id']}.zip"})
    pd.DataFrame(rows).reindex(columns=COLS, fill_value="").fillna("").to_csv(paths.manifest, index=False)
    mus = read_table(ROOT / "data" / "music_bpm.csv")
    mus["duration_s"] = music_duration
    mus.to_csv(paths.music, index=False)
    par = read_table(ROOT / "data" / "participants.csv")
    par["section_distance_m"] = distance
    par.to_csv(paths.participants, index=False)
    d0, d1 = np.degrees(150 / R_EARTH), np.degrees(350 / R_EARTH)
    pd.DataFrame([dict(participant="A", seq=s, lat=0.001 + d, lon=0.001, label="합성")
                  for s, d in ((1, d0), (2, d1))]).to_csv(paths.sections, index=False)
    return paths, read_table(paths.manifest).to_dict("records")


def _status(checks, wid, cid):
    return {(c.walk_id, c.check_id): c.status for c in checks}[(wid, cid)]


E1 = dict(experiment="E1", participant="A", walk_no="1", date="2026-11-09", condition="S", start_song="")
GOOD = dict(walk_s=500, seed=11)


def test_good_e1_walk_passes(tmp_path, params):
    paths, rows = _env(tmp_path, [({**E1, "walk_id": "E1_A_01_S_1109", "hand_step_count": ""}, SynthSpec(**GOOD))])
    checks, _ = run_checks(rows, paths, params)
    for cid in ("Q01", "Q02", "Q03", "Q04", "Q05", "Q07", "Q08a", "Q08b", "Q09", "Q10", "Q11", "Q13b"):
        assert _status(checks, "E1_A_01_S_1109", cid) == "PASS", cid
    assert _status(checks, "E1_A_01_S_1109", "Q12") == "NA"  # 무음
    assert _status(checks, "ALL", "Q15") == "PASS"


def test_failures_and_warnings(tmp_path, params):
    files, _ = make_files(SynthSpec(walk_s=60, seed=12))
    loc = pd.read_csv(io.BytesIO(files["Location.csv"]))
    loc["horizontalAccuracy"] = 30.0
    acc, grav = (pd.read_csv(io.BytesIO(files[n])) for n in ("Accelerometer.csv", "Gravity.csv"))
    acc[["x", "y", "z"]] = 0.5 * grav[["x", "y", "z"]].to_numpy()
    short = dict(walk_s=60)
    walks = [
        ({**E1, "walk_id": "E1_A_01_S_1109", "hand_step_count": "50"},  # Q04 짧음, Q06 틀림, Q08b 정확도
         SynthSpec(**short, seed=13, extra_files={"Location.csv": loc.to_csv(index=False).encode()})),
        ({**E1, "walk_id": "E1_A_02_P1_1110", "walk_no": "2", "date": "2026-11-11", "condition": "P1",
          "start_song": "2"}, SynthSpec(**short, seed=14, fs_hz=40, pedometer_factor=1.2)),  # Q02·Q07·Q10·Q11
        ({**E1, "walk_id": "E1_A_03_P2_1109", "walk_no": "3", "condition": "P2", "start_song": "1"},
         SynthSpec(**short, seed=15, gaps=((40.0, 1.5),), stand_start_s=0, stand_end_s=0)),  # Q03 FAIL, Q05 WARN
        ({**E1, "walk_id": "E1_A_04_P3_1109", "walk_no": "4", "condition": "P3", "start_song": "1"},
         SynthSpec(**short, seed=16, extra_files={"Accelerometer.csv": acc.to_csv(index=False).encode()})),  # Q09
        ({**E1, "walk_id": "E1_A_05_P4_1109", "walk_no": "5", "condition": "P4", "start_song": "1"},
         SynthSpec(**short, seed=17, extra_files={"Location.csv": b""})),  # Q01 필수 없음
    ]
    paths, rows = _env(tmp_path, walks, distance="150", music_duration="")
    checks, _ = run_checks(rows, paths, params)
    s = lambda w, c: _status(checks, w, c)  # noqa: E731
    assert s("E1_A_01_S_1109", "Q04") == "FAIL" and s("E1_A_01_S_1109", "Q06") == "FAIL"
    assert s("E1_A_01_S_1109", "Q08b") == "WARN"
    assert s("E1_A_02_P1_1110", "Q02") == "FAIL" and s("E1_A_02_P1_1110", "Q07") == "WARN"
    assert s("E1_A_02_P1_1110", "Q10") == "FAIL" and s("E1_A_02_P1_1110", "Q11") == "FAIL"
    assert s("E1_A_02_P1_1110", "Q12") == "FAIL"  # duration_s가 비었다
    assert s("E1_A_03_P2_1109", "Q03") == "FAIL" and s("E1_A_03_P2_1109", "Q05") == "WARN"
    assert s("E1_A_04_P3_1109", "Q09") == "FAIL"
    assert s("E1_A_05_P4_1109", "Q01") == "FAIL"


def test_q08a_and_q14_and_q15(tmp_path, params):
    walks = [({**E1, "walk_id": f"E1_A_0{i}_S_1109", "walk_no": str(i)},
              SynthSpec(walk_s=300, seed=20 + i, orientation="landscape" if i == 3 else "portrait"))
             for i in (1, 2, 3)]
    paths, rows = _env(tmp_path, walks, distance="150")  # GPS로는 200 m
    checks, _ = run_checks(rows, paths, params)
    assert _status(checks, "E1_A_01_S_1109", "Q08a") == "WARN"
    assert _status(checks, "E1_A_03_S_1109", "Q14") == "WARN"  # 혼자 가로
    assert _status(checks, "E1_A_01_S_1109", "Q14") == "PASS"
    leak = paths.results / "leak.csv"
    pd.DataFrame({"walk_id": ["x"], "latitude": [37.5]}).to_csv(leak, index=False)
    checks, _ = run_checks(rows[:1], paths, params)
    assert _status(checks, "ALL", "Q15") == "FAIL"


def test_synthetic_gate_g1_all_pass(tmp_path, params):
    s = Paths(tmp_path / "data" / "raw", tmp_path / "data" / "manifest.csv", ROOT / "data" / "assignment.csv",
              tmp_path / "data" / "music.csv", tmp_path / "data" / "participants.csv",
              tmp_path / "data" / "private" / "sections.csv", tmp_path)
    make_synthetic_dataset(s, params)
    manifest = read_table(s.manifest)
    checks, _ = run_checks(manifest.to_dict("records"), s, params)
    g = gate_g1(checks, manifest)
    assert list(g["participant"]) == ["A", "B", "C"]
    assert (g["first_data"] == "2/2").all()
    for col in ("background", "hand_100", "gps", "names_assignment_units"):
        assert (g[col] == "PASS").all(), col
    assert _status(checks, "ALL", "Q15") == "PASS"


def test_real_files_qa(tmp_path, params):
    for p in (TRIAL, *PRECHECK.values()):
        real(p)
    real_paths = Paths.real()
    paths = Paths(real_paths.raw, real_paths.manifest, real_paths.assignment, real_paths.music,
                  real_paths.participants, real_paths.sections, tmp_path)
    rows = read_table(paths.manifest).to_dict("records")
    checks, _ = run_checks(rows, paths, params)
    s = lambda w, c: _status(checks, w, c)  # noqa: E731
    assert all(s(w, "Q09") == "PASS" and s(w, "Q03") == "PASS" for w in [r["walk_id"] for r in rows])
    assert s("TEST_A_1108_2", "Q06") == "PASS"
    assert s("ALL", "Q15") == "PASS"
