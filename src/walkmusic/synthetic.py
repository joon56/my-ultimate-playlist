"""실제 형식을 흉내 낸 합성 Sensor Logger zip (SPEC §10, DATA_FACTS §1–§7·§10).

형식: iOS·standardisation=false 시범 파일과 같다. 열 순서 time, seconds_elapsed, z, y, x.
Accelerometer = 중력 제외(m/s²), Gravity = 땅 쪽 단위 벡터 × 9.80665(m/s²),
AccelerometerUncalibrated = Accelerometer + Gravity를 g로(D-29). 좌표는 0 근처 가짜 값(SPEC §11).
같은 SynthSpec(시드 포함)이면 같은 바이트의 zip이 나온다.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

G0 = 9.80665
# 몸 기준 축(앞뒤 AP, 좌우 ML, 위 UP) → 폰 축(x, y, z). 열이 몸 축의 폰 좌표.
FRAMES = {
    "portrait": np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], float),   # 위 = +y (Gravity ≈ −y)
    "landscape": np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], float),  # 위 = +x (Gravity ≈ −x)
}
META_SENSORS = ("Accelerometer|Gravity|Gyroscope|Location|Pedometer|Annotation|"
                "GyroscopeUncalibrated|AccelerometerUncalibrated")


@dataclass
class SynthSpec:
    """합성 기록 하나의 설정(시간 단위 s, 가속도 단위 g)."""

    walk_s: float = 120.0
    cadence_spm: float = 110.0
    interval_cv_pct: float = 2.0
    n_walk_steps: int | None = None   # 주면 walk_s 대신 이 걸음 수로 걷는다(100걸음 시험)
    amp_g: float = 0.5
    amp_cv_pct: float = 10.0
    noise_g: float = 0.02
    orientation: str = "portrait"
    handling_s: float = 3.0
    pre_walk_steps: int = 0
    stand_start_s: float = 10.0
    stand_end_s: float = 10.0
    post_handling_s: float = 3.0
    fidget_bumps: int = 0
    fidget_g: float = 0.04             # 서 있을 때 흔들림 크기(실제 파우치 서 있기는 0.08 g 이하)
    fs_hz: float = 99.58
    gaps: tuple[tuple[float, float], ...] = ()
    speed_mps: float = 1.3
    pedometer_factor: float = 1.0
    epoch_ms: int = 1_800_000_000_000
    seed: int = 0
    extra_files: dict[str, bytes] = field(default_factory=dict)


@dataclass
class SynthTruth:
    """합성 기록의 정답."""

    step_times_s: np.ndarray
    pre_step_times_s: np.ndarray
    t_depart: float
    t_arrive: float
    stand_start: tuple[float, float]
    stand_end: tuple[float, float]
    duration_s: float
    cadence_spm: float


def _step_times(rng: np.random.Generator, t0: float, n: int, cadence: float, cv_pct: float) -> np.ndarray:
    iv = 60.0 / cadence * (1 + cv_pct / 100.0 * rng.standard_normal(n))
    return t0 + np.concatenate([[0.0], np.cumsum(iv[:-1])])


def _body_force(t: np.ndarray, steps: np.ndarray, amps: np.ndarray, cadence: float) -> np.ndarray:
    """걷는 동안 몸 기준 비력(g): 위쪽 발 디딤 봉우리 + 앞뒤 흔들림 + 한 보에 한 번 좌우 흔들림."""
    f_step = cadence / 60.0
    up = np.zeros_like(t)
    for tk, ak in zip(steps, amps, strict=True):
        sel = np.abs(t - tk) < 0.25
        up[sel] += ak * np.exp(-0.5 * ((t[sel] - tk) / 0.035) ** 2)
    active = (t >= steps[0] - 0.3) & (t <= steps[-1] + 0.3)
    if active.any():
        up[active] -= up[active].mean()  # 걷는 동안 평균 1 g를 지킨다
    ap = 0.15 * np.sin(2 * np.pi * f_step * t) * active
    ml = 0.10 * np.sin(np.pi * f_step * t) * active
    return np.column_stack([ap, ml, up])


def make_files(spec: SynthSpec) -> tuple[dict[str, bytes], SynthTruth]:
    """zip에 들어갈 파일 이름 → 바이트와 정답을 만든다."""
    rng = np.random.default_rng(spec.seed)
    period = 60.0 / spec.cadence_spm
    t_pre0 = spec.handling_s + 0.5
    pre = _step_times(rng, t_pre0, spec.pre_walk_steps, spec.cadence_spm, spec.interval_cv_pct) \
        if spec.pre_walk_steps else np.array([])
    stand0 = (pre[-1] + period if len(pre) else spec.handling_s)
    stand1 = stand0 + spec.stand_start_s
    t_dep = stand1 + 0.3
    n_walk = spec.n_walk_steps or int(spec.walk_s / period)
    walk = _step_times(rng, t_dep, n_walk, spec.cadence_spm, spec.interval_cv_pct)
    end0 = walk[-1] + 0.4
    end1 = end0 + spec.stand_end_s
    duration = end1 + spec.post_handling_s

    dt = 1.0 / spec.fs_hz
    t = 0.058 + np.arange(int((duration - 0.058) / dt)) * dt
    for g0, glen in spec.gaps:
        t = t[(t < g0) | (t >= g0 + glen)]

    all_steps = np.concatenate([pre, walk])
    amps = spec.amp_g * (1 + spec.amp_cv_pct / 100.0 * rng.standard_normal(len(all_steps)))
    fb = _body_force(t, all_steps, amps, spec.cadence_spm) if len(all_steps) else np.zeros((len(t), 3))
    if len(pre):  # 앞 걷기와 본 걷기 사이 서 있기에는 흔들림을 끈다
        between = (t > pre[-1] + 0.3) & (t < walk[0] - 0.3)
        fb[between, :2] = 0.0
    for a, b in ((stand0, stand1), (end0, end1)):  # 서 있는 동안의 작은 흔들림
        for tk in rng.uniform(a + 1, b - 1, spec.fidget_bumps):
            sel = np.abs(t - tk) < 0.4
            fb[sel, 2] += spec.fidget_g * np.exp(-0.5 * ((t[sel] - tk) / 0.12) ** 2)
    fb[:, 2] += 1.0

    # 폰 방향: 처음에는 손(파우치 방향에서 70° 기울임), 넣으면 파우치 방향, 끝에 다시 손
    R_pouch = Rotation.from_matrix(FRAMES[spec.orientation])
    tilt = Rotation.from_euler("x", 70, degrees=True)
    rot_t = np.zeros(len(t))
    tin, tout = spec.handling_s - 1.0, end1 + 1.0
    rot_t[t < tin] = 1.0
    sel = (t >= tin) & (t < spec.handling_s)
    rot_t[sel] = 1 - (t[sel] - tin) / 1.0
    sel = (t >= end1) & (t < tout)
    rot_t[sel] = (t[sel] - end1) / 1.0
    rot_t[t >= tout] = 1.0
    rots = R_pouch * Rotation.from_rotvec(np.outer(rot_t, tilt.as_rotvec()))
    f_dev = rots.apply(fb)
    handling = rot_t > 0
    f_dev[handling] += 0.15 * rng.standard_normal((int(handling.sum()), 3))
    down = rots.apply(np.tile([0.0, 0.0, -1.0], (len(t), 1)))
    reading_g = -f_dev + spec.noise_g * rng.standard_normal(f_dev.shape)   # iOS 원값 = −비력
    grav = G0 * down
    accel = G0 * reading_g - grav
    uncal = reading_g  # 실제 파일도 Accelerometer + Gravity = 9.80665 × Uncalibrated (DATA_FACTS §4)
    gyro = np.column_stack([0.3 * np.sin(np.pi * spec.cadence_spm / 60 * t), 0.2 * np.sin(0.7 * t),
                            0.1 * np.sin(1.3 * t)]) * (fb[:, 0] != 0)[:, None]
    gyro += 0.02 * rng.standard_normal(gyro.shape)
    gyro[handling] += 2.0 * rng.standard_normal((int(handling.sum()), 3))

    epoch_ns = spec.epoch_ms * 10**6
    time_ns = epoch_ns + np.round(t * 1e9).astype("int64")

    def imu_csv(v: np.ndarray) -> bytes:
        df = pd.DataFrame({"time": time_ns, "seconds_elapsed": np.round(t, 6), "z": v[:, 2], "y": v[:, 1],
                           "x": v[:, 0]})
        return df.to_csv(index=False, float_format="%.9g", lineterminator="\n").encode()

    files = {"Accelerometer.csv": imu_csv(accel), "Gravity.csv": imu_csv(grav), "Gyroscope.csv": imu_csv(gyro),
             "AccelerometerUncalibrated.csv": imu_csv(uncal), "GyroscopeUncalibrated.csv": imu_csv(gyro + 0.004)}

    # 위치: 1 Hz, 기록 전 점 2개, 걷는 동안 북쪽으로 이동(0 근처 가짜 좌표)
    lt = np.r_[-14.2, -5.2, 0.05 + np.arange(int(duration))]
    moving = (lt >= t_dep) & (lt <= walk[-1])
    dist = np.cumsum(np.r_[0, np.diff(lt)] * moving * spec.speed_mps)
    lat = 0.001 + np.degrees(dist / 6371008.8) + np.degrees(rng.normal(0, 0.3, len(lt)) / 6371008.8)
    lon = 0.001 + np.degrees(rng.normal(0, 0.3, len(lt)) / 6371008.8)
    speed = np.where(moving, spec.speed_mps + rng.normal(0, 0.05, len(lt)), 0.0)
    speed[lt < 2.5] = -1.0
    loc = pd.DataFrame({"time": epoch_ns + np.round(lt * 1e9).astype("int64"), "seconds_elapsed": lt,
                        "altitude": 30.0, "speedAccuracy": np.where(speed < 0, -1.0, 0.9), "bearingAccuracy": 60.0,
                        "latitude": lat, "altitudeAboveMeanSeaLevel": 30.0, "bearing": 0.0,
                        "horizontalAccuracy": 4.75, "verticalAccuracy": 5.0, "longitude": lon, "speed": speed})
    files["Location.csv"] = loc.to_csv(index=False, float_format="%.10g", lineterminator="\n").encode()

    pt = all_steps[0] + 5.0 + 2.5706 * np.arange(int((duration - all_steps[0] - 5.0) / 2.5706)) \
        if len(all_steps) else np.array([])
    pv = np.floor(spec.pedometer_factor * np.searchsorted(all_steps, pt, side="right"))
    ped = pd.DataFrame({"time": epoch_ns + np.round(pt * 1e9).astype("int64"), "seconds_elapsed": pt,
                        "steps": pv.astype(int)})
    files["Pedometer.csv"] = ped.to_csv(index=False, float_format="%.6f", lineterminator="\n").encode()

    rec_time = pd.Timestamp(epoch_ns, unit="ns", tz="UTC").strftime("%Y-%m-%d_%H-%M-%S")
    meta = pd.DataFrame([{"version": "3", "device name": "SYNTHETIC-DEVICE", "recording epoch time": spec.epoch_ms,
                          "recording time": rec_time, "recording timezone": "Asia/Seoul", "platform": "ios",
                          "appVersion": "1.68.1", "device id": "00000000-SYNTH-0000",
                          "sensors": META_SENSORS, "sampleRateMs": "10|10|10|0|10||10|10",
                          "standardisation": "false", "platform version": "26.2.1"}])
    files["Metadata.csv"] = meta.to_csv(index=False, lineterminator="\n").encode().rstrip(b"\n")
    files["Annotation.csv"] = b""
    files.update(spec.extra_files)
    truth = SynthTruth(step_times_s=walk, pre_step_times_s=pre, t_depart=float(walk[0]), t_arrive=float(walk[-1]),
                       stand_start=(float(stand0), float(stand1)), stand_end=(float(end0), float(end1)),
                       duration_s=float(t[-1] - t[0]), cadence_spm=spec.cadence_spm)
    return files, truth


def write_zip(path: str | Path, spec: SynthSpec) -> SynthTruth:
    """합성 zip을 path에 쓰고 정답을 돌려준다. 같은 spec이면 같은 바이트."""
    files, truth = make_files(spec)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    Path(path).write_bytes(buf.getvalue())
    return truth
