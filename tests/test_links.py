"""zip ↔ manifest 연결과 walk_id (SPEC §3.4, DECISIONS D-27)."""

import pandas as pd
import pytest

from walkmusic.io_sensorlogger import read_start_epoch
from walkmusic.links import expected_walk_id, fill_walk_ids, find_zip, propose_links, write_zip_links
from walkmusic.synthetic import SynthSpec, write_zip

TZ = "Asia/Seoul"


def kst_ms(s: str) -> int:
    return int(pd.Timestamp(s, tz=TZ).value // 10**6)


def row(**kw):
    base = dict(walk_id="", experiment="E1", participant="B", walk_no="7", date="2026-11-13", start_time="08:42",
                condition="P1", zip_file="")
    return {**base, **kw}


def _zips(tmp_path, specs):
    """specs: {(사람, zip 이름): 'YYYY-MM-DD HH:MM:SS'(KST 기록 시작)} → data/raw/<사람>/<이름>."""
    raw = tmp_path / "raw"
    for (p, name), t in specs.items():
        (raw / p).mkdir(parents=True, exist_ok=True)
        write_zip(raw / p / name, SynthSpec(walk_s=20, epoch_ms=kst_ms(t)))
    return raw


def test_expected_walk_id_e1():
    assert expected_walk_id(row()) == "E1_B_07_P1_1113"
    assert expected_walk_id(row(walk_no="16", condition="S", date="2026-11-21")) == "E1_B_16_S_1121"


def test_fill_walk_ids_keeps_given_and_numbers_tests():
    rows = [row(), row(walk_id="E1_B_08_P2_1114", walk_no="8", condition="P2", date="2026-11-14"),
            row(experiment="TEST", walk_no="", condition="steps100", date="2026-11-10"),
            row(experiment="TEST", walk_no="", condition="steps100", date="2026-11-10"),
            row(experiment="TEST", walk_no="", condition="rehearsal", date="2026-11-10")]
    ids = [r["walk_id"] for r in fill_walk_ids(rows)]
    assert ids == ["E1_B_07_P1_1113", "E1_B_08_P2_1114", "TEST_B_1110_steps100", "TEST_B_1110_steps100_2",
                   "TEST_B_1110_rehearsal"]
    assert rows[0]["walk_id"] == ""  # 입력(manifest)은 고치지 않는다


def test_read_start_epoch_metadata_then_imu(tmp_path):
    ms = kst_ms("2026-11-13 08:42:37.250")
    write_zip(tmp_path / "a.zip", SynthSpec(walk_s=20, epoch_ms=ms))
    assert read_start_epoch(tmp_path / "a.zip") == (ms * 10**6, "metadata")
    write_zip(tmp_path / "b.zip", SynthSpec(walk_s=20, epoch_ms=ms, extra_files={"Metadata.csv": b""}))
    epoch, source = read_start_epoch(tmp_path / "b.zip")
    assert source == "imu_first" and 0 <= epoch - ms * 10**6 < 100 * 10**6  # 첫 IMU 샘플은 수십 ms 뒤


def test_propose_links_matched_none_ambiguous(tmp_path):
    raw = _zips(tmp_path, {("B", "b1.zip"): "2026-11-13 08:42:37", ("B", "b2.zip"): "2026-11-13 18:10:30",
                           ("B", "b3.zip"): "2026-11-13 12:00:00", ("C", "c1.zip"): "2026-11-13 08:42:50"})
    rows = [row(), row(walk_no="8", start_time="18:10"), row(walk_no="9", start_time="18:11"),
            row(participant="C")]
    links = propose_links(rows, raw, tol_s=90, tz=TZ).set_index("zip_name")
    assert links.loc["b1.zip", "status"] == "matched" and links.loc["b1.zip", "walk_id"] == "E1_B_07_P1_1113"
    assert float(links.loc["b1.zip", "diff_s"]) == pytest.approx(37.0)
    assert links.loc["b1.zip", "start_kst"].startswith("2026-11-13 08:42:37")
    assert links.loc["b2.zip", "status"] == "ambiguous"  # 18:10과 18:11 줄 둘 다 90 s 안
    assert links.loc["b2.zip", "walk_id"] == "E1_B_08_P1_1113|E1_B_09_P1_1113"
    assert links.loc["b3.zip", "status"] == "none" and links.loc["b3.zip", "walk_id"] == ""
    assert links.loc["c1.zip", "status"] == "matched" and links.loc["c1.zip", "walk_id"] == "E1_C_07_P1_1113"


def test_two_zips_for_one_row_are_ambiguous(tmp_path):
    raw = _zips(tmp_path, {("B", "x.zip"): "2026-11-13 08:42:10", ("B", "y.zip"): "2026-11-13 08:43:00"})
    assert set(propose_links([row()], raw, tol_s=90, tz=TZ)["status"]) == {"ambiguous"}


def test_find_zip_person_folder_then_flat(tmp_path):
    raw = _zips(tmp_path, {("B", "b1.zip"): "2026-11-13 08:42:37"})
    write_zip(raw / "old.zip", SynthSpec(walk_s=20))
    assert find_zip(raw, row(zip_file="b1.zip")) == raw / "B" / "b1.zip"
    assert find_zip(raw, row(zip_file="old.zip")) == raw / "old.zip"
    assert find_zip(raw, row(walk_id="E1_B_07_P1_1113")) == raw / "E1_B_07_P1_1113.zip"  # zip_file이 없으면


def test_write_zip_links_csv(tmp_path, params):
    raw = _zips(tmp_path, {("B", "b1.zip"): "2026-11-13 08:42:37"})
    man = tmp_path / "manifest.csv"
    pd.DataFrame([row()]).to_csv(man, index=False)
    write_zip_links(man, raw, tmp_path / "results", params)
    df = pd.read_csv(tmp_path / "results" / "zip_links.csv", dtype=str, keep_default_na=False)
    assert list(df.columns) == ["zip_name", "participant", "start_kst", "walk_id", "diff_s", "status"]
    assert df.loc[0, "status"] == "matched"
