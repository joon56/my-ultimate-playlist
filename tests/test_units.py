"""단위·중력 포함·합성 부호 판별: 합성 4가지 규약 × 세로·가로, 실제 4개 파일."""

import io

import numpy as np
import pandas as pd
import pytest

from conftest import PRECHECK, TRIAL, real
from walkmusic.io_sensorlogger import read_zip
from walkmusic.orientation import vertical_signal
from walkmusic.synthetic import G0, SynthSpec, make_files, write_zip
from walkmusic.units import UnitsError, determine_units, total_accel_g


def _variant(tmp_path, kind: str, orientation: str):
    """시범 형식(중력 제외, +1)을 바꿔 다른 규약의 zip을 만든다."""
    files, truth = make_files(SynthSpec(walk_s=40, orientation=orientation))
    rd = lambda n: pd.read_csv(io.BytesIO(files[n]))  # noqa: E731
    acc, grav = rd("Accelerometer.csv"), rd("Gravity.csv")
    xyz = ["x", "y", "z"]
    a, g = acc[xyz].to_numpy(), grav[xyz].to_numpy()
    if kind == "incl_g":
        a, g = (a + g) / G0, g / G0
    elif kind == "incl_ms2":
        a = a + g
    elif kind == "excl_minus":
        g = -g
    acc[xyz], grav[xyz] = a, g
    extra = {"Accelerometer.csv": acc.to_csv(index=False).encode(), "Gravity.csv": grav.to_csv(index=False).encode()}
    if kind != "excl_plus":
        extra["AccelerometerUncalibrated.csv"] = b""  # 다른 규약에서는 Uncalibrated 교차 확인 없이
    p = tmp_path / f"{kind}_{orientation}.zip"
    write_zip(p, SynthSpec(walk_s=40, orientation=orientation, extra_files=extra))
    return p, truth


@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
@pytest.mark.parametrize("kind, units, incl, sign", [
    ("excl_plus", "m/s2", False, 1), ("excl_minus", "m/s2", False, -1),
    ("incl_ms2", "m/s2", True, 0), ("incl_g", "g", True, 0)])
def test_conventions(tmp_path, kind, units, incl, sign, orientation):
    p, truth = _variant(tmp_path, kind, orientation)
    rec = read_zip(p)
    u = determine_units(rec)
    assert (u.accel_units, u.includes_gravity, u.combine_sign) == (units, incl, sign)
    t, total, g = total_accel_g(rec, u)
    v = vertical_signal(total, g)
    still = (t > truth.stand_start[0] + 1) & (t < truth.stand_start[1] - 1)
    assert np.median(v[still]) == pytest.approx(1.0, abs=0.05)  # 서 있을 때 +1 g
    walk = (t > truth.t_depart) & (t < truth.t_arrive)
    assert np.percentile(v[walk], 99) - np.median(v[walk]) > np.median(v[walk]) - np.percentile(v[walk], 1)


def test_unresolvable_raises(tmp_path):
    files, _ = make_files(SynthSpec(walk_s=20))
    acc, grav = (pd.read_csv(io.BytesIO(files[n])) for n in ("Accelerometer.csv", "Gravity.csv"))
    acc[["x", "y", "z"]] = 0.5 * grav[["x", "y", "z"]].to_numpy()  # 중력의 절반: 포함도 제외도 아니다
    p = tmp_path / "bad.zip"
    write_zip(p, SynthSpec(walk_s=20, extra_files={"Accelerometer.csv": acc.to_csv(index=False).encode()}))
    with pytest.raises(UnitsError):
        determine_units(read_zip(p))


@pytest.mark.parametrize("path", [TRIAL, *PRECHECK.values()], ids=["trial", "pre1", "pre2", "pre3"])
def test_real_files(path):
    u = determine_units(read_zip(real(path)))
    assert (u.accel_units, u.includes_gravity, u.combine_sign, u.confidence) == ("m/s2", False, 1, "high")
    assert u.g_scale == pytest.approx(9.80665, abs=1e-4)
