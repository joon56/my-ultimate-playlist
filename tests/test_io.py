"""zip 불러오기·시간축·inspect, 합성 생성기의 형식."""

import numpy as np
import pandas as pd
import pytest

from conftest import PRECHECK, TRIAL, real
from walkmusic.io_sensorlogger import inspect_report, read_zip, uniform_segments
from walkmusic.synthetic import SynthSpec, make_files, write_zip


def test_synthetic_same_seed_same_bytes(tmp_path):
    a, b, c = tmp_path / "a.zip", tmp_path / "b.zip", tmp_path / "c.zip"
    write_zip(a, SynthSpec(walk_s=20, seed=1))
    write_zip(b, SynthSpec(walk_s=20, seed=1))
    write_zip(c, SynthSpec(walk_s=20, seed=2))
    assert a.read_bytes() == b.read_bytes() != c.read_bytes()


@pytest.mark.parametrize("orientation, axis", [("portrait", 1), ("landscape", 0)])
def test_synthetic_units_and_orientation(make_synth, orientation, axis):
    path, truth = make_synth(walk_s=30, orientation=orientation)
    rec = read_zip(path)
    g = rec.xyz("Gravity")
    assert np.allclose(np.linalg.norm(g, axis=1), 9.80665)
    sel = (rec.t("Gravity") > truth.t_depart) & (rec.t("Gravity") < truth.t_arrive)
    down = np.median(g[sel], axis=0) / 9.80665
    assert down[axis] == pytest.approx(-1.0, abs=0.02)  # 세로는 −y, 가로는 −x
    total = rec.xyz("Accelerometer") + g
    assert np.median(np.linalg.norm(total - 9.80665 * rec.xyz("AccelerometerUncalibrated"), axis=1)) < 0.05


def test_read_synthetic_structure(make_synth, params):
    path, truth = make_synth(walk_s=30)
    rec = read_zip(path)
    assert set(rec.files) == {"Accelerometer.csv", "AccelerometerUncalibrated.csv", "Annotation.csv", "Gravity.csv",
                              "Gyroscope.csv", "GyroscopeUncalibrated.csv", "Location.csv", "Metadata.csv",
                              "Pedometer.csv"}
    assert rec.empty == ["Annotation"] and rec.unknown == []
    assert rec.epoch_source == "metadata"
    assert rec.t("Accelerometer")[0] == pytest.approx(0.058, abs=1e-3)
    assert rec.dropped["Location"] == 2 and rec.t("Location").min() >= 0
    assert "device name" not in rec.meta and "device id" not in rec.meta
    assert np.isnan(rec.sensors["Location"]["speed"].iloc[0])  # −1은 무효 → NaN


def test_columns_read_by_name(tmp_path):
    files, _ = make_files(SynthSpec(walk_s=10))
    df = pd.read_csv(pd.io.common.BytesIO(files["Accelerometer.csv"]))
    shuffled = df[["time", "x", "seconds_elapsed", "y", "z"]].to_csv(index=False).encode()
    p1, p2 = tmp_path / "a.zip", tmp_path / "b.zip"
    write_zip(p1, SynthSpec(walk_s=10))
    write_zip(p2, SynthSpec(walk_s=10, extra_files={"Accelerometer.csv": shuffled}))
    assert np.allclose(read_zip(p1).xyz("Accelerometer"), read_zip(p2).xyz("Accelerometer"))


def test_epoch_fallback_without_metadata(tmp_path):
    p = tmp_path / "nometa.zip"
    write_zip(p, SynthSpec(walk_s=10, extra_files={"Metadata.csv": b""}))
    rec = read_zip(p)
    assert rec.epoch_source == "imu_first" and rec.t("Accelerometer")[0] == 0.0


def test_uniform_segments_do_not_cross_gaps():
    t = np.r_[np.arange(0, 5, 0.01), np.arange(6.0, 8, 0.01)]
    segs = uniform_segments(t, np.sin(t), 0.25)
    assert len(segs) == 2
    assert segs[0][0][-1] < 5.0 <= 6.0 <= segs[1][0][0] + 1e-9


def test_inspect_has_no_private_values(make_synth):
    path, _ = make_synth(walk_s=30)
    rec = read_zip(path)
    text = inspect_report(rec)
    lat = rec.sensors["Location"]["latitude"].to_numpy()
    assert "SYNTHETIC-DEVICE" not in text and "SYNTH-0000" not in text
    assert not any(f"{v:.5f}" in text for v in lat)
    assert "t_s" in text and "Annotation" in text


def test_real_trial_matches_data_facts():
    rec = read_zip(real(TRIAL))
    assert len(rec.sensors["Accelerometer"]) == 71588 and len(rec.sensors["Pedometer"]) == 275
    assert rec.kst(rec.t("Accelerometer")[0]).strftime("%H:%M:%S.%f")[:-3] == "20:20:44.502"
    assert rec.dropped["Location"] == 2
    assert 1 / np.median(np.diff(rec.t("Accelerometer"))) == pytest.approx(99.58, abs=0.01)


@pytest.mark.parametrize("n, rows, start", [(1, 66409, "19:29:52.533"), (2, 11434, "19:42:32.691"),
                                            (3, 25399, "19:47:56.740")])
def test_real_precheck_matches_data_facts(n, rows, start):
    rec = read_zip(real(PRECHECK[n]))
    assert len(rec.sensors["Accelerometer"]) == rows
    assert rec.kst(0).strftime("%H:%M:%S.%f")[:-3] == start
