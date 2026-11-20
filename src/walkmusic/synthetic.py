"""실제 형식을 흉내 낸 합성 Sensor Logger zip (SPEC §10, DATA_FACTS §1–§7·§10).

형식: iOS·standardisation=false 시범 파일과 같다. 열 순서 time, seconds_elapsed, z, y, x.
Accelerometer = 중력 제외(m/s²), Gravity = 땅 쪽 단위 벡터 × 9.80665(m/s²),
AccelerometerUncalibrated = Accelerometer + Gravity를 g로(D-44). 좌표는 0 근처 가짜 값(SPEC §11).
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
    # (기록 시각 t_s, 값): 그 시각부터 케이던스(spm)·이동 속도(m/s)를 바꾼다. 비면 cadence_spm·speed_mps 고정
    cadence_schedule: tuple[tuple[float, float], ...] = ()
    speed_schedule: tuple[tuple[float, float], ...] = ()


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


def _scheduled(schedule: tuple[tuple[float, float], ...], t: np.ndarray | float, default: float) -> np.ndarray:
    """(시각, 값) 계단 함수의 t에서의 값. 첫 시각 전에는 default."""
    times = np.array([s[0] for s in schedule])
    vals = np.r_[default, [s[1] for s in schedule]]
    return vals[np.searchsorted(times, np.asarray(t, float), side="right")]


def _scheduled_steps(rng: np.random.Generator, t0: float, t_end: float, spec: SynthSpec) -> np.ndarray:
    """케이던스 계획대로 t0부터 t_end까지 걸음 시각을 만든다."""
    steps, t = [t0], t0
    while True:
        c = float(_scheduled(spec.cadence_schedule, t, spec.cadence_spm))
        t += 60.0 / c * (1 + spec.interval_cv_pct / 100.0 * rng.standard_normal())
        if t > t_end:
            return np.array(steps)
        steps.append(t)


def _body_force(t: np.ndarray, steps: np.ndarray, amps: np.ndarray, cadence: float,
                follow_steps: bool = False) -> np.ndarray:
    """걷는 동안 몸 기준 비력(g): 위쪽 발 디딤 봉우리 + 앞뒤 흔들림 + 한 보에 한 번 좌우 흔들림.

    follow_steps이면 앞뒤·좌우 흔들림의 위상을 걸음 시각에 맞춘다(케이던스가 바뀌는 기록).
    """
    f_step = cadence / 60.0
    up = np.zeros_like(t)
    for tk, ak in zip(steps, amps, strict=True):
        sel = np.abs(t - tk) < 0.25
        up[sel] += ak * np.exp(-0.5 * ((t[sel] - tk) / 0.035) ** 2)
    active = (t >= steps[0] - 0.3) & (t <= steps[-1] + 0.3)
    if active.any():
        up[active] -= up[active].mean()  # 걷는 동안 평균 1 g를 지킨다
    phase = np.interp(t, steps, np.arange(len(steps))) if follow_steps else f_step * t
    ap = 0.15 * np.sin(2 * np.pi * phase) * active
    ml = 0.10 * np.sin(np.pi * phase) * active
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
    if spec.cadence_schedule:
        walk = _scheduled_steps(rng, t_dep, t_dep + spec.walk_s, spec)
    else:
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
    fb = _body_force(t, all_steps, amps, spec.cadence_spm, bool(spec.cadence_schedule)) \
        if len(all_steps) else np.zeros((len(t), 3))
    if len(pre):  # 앞 걷기와 본 걷기 사이 서 있기에는 흔들림을 끈다
        between = (t > pre[-1] + 0.3) & (t < walk[0] - 0.3)
        fb[between, :2] = 0.0
    for a, b in ((stand0, stand1), (end0, end1)):  # 서 있는 동안의 작은 흔들림
        if spec.fidget_bumps == 0 or b - a <= 2:
            continue
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
    v_now = _scheduled(spec.speed_schedule, lt, spec.speed_mps)
    dist = np.cumsum(np.r_[0, np.diff(lt) * moving[1:] * v_now[:-1]])
    lat = 0.001 + np.degrees(dist / 6371008.8) + np.degrees(rng.normal(0, 0.15, len(lt)) / 6371008.8)
    lon = 0.001 + np.degrees(rng.normal(0, 0.15, len(lt)) / 6371008.8)
    speed = np.where(moving, v_now + rng.normal(0, 0.05, len(lt)), 0.0)
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


# --- 실험 3 · 다리 진자 (SPEC §10: 알려진 흔들림 주기의 합성 자이로) ---


@dataclass
class SwingSpec:
    """합성 진자 기록 하나(정강이에 붙인 폰). 시간 s, 각속도 rad/s."""

    period_s: float = 1.55
    omega_amp_rad_s: float = 2.0
    swing_s: float = 20.0
    decay_per_s: float = 0.02          # 진폭이 e^(−decay·t)로 줄어든다
    handling_s: float = 3.0            # 처음·끝에 폰을 만지는 시간(세 축 모두 크게 흔들림)
    still_s: float = 2.0               # 흔들기 전후 가만히
    handling_rad_s: float = 1.5
    noise_rad_s: float = 0.03
    axis: tuple[float, float, float] = (0.25, 0.92, 0.30)  # 흔들림 회전축(폰 좌표)
    fs_hz: float = 99.58
    epoch_ms: int = 1_800_000_000_000
    seed: int = 0


def make_swing_gyro(spec: SwingSpec) -> tuple[np.ndarray, np.ndarray, dict]:
    """(t_s, Gyroscope N×3 rad/s, 정답). 정답 amp_deg는 흔들기 가운데 시각의 진폭(ω 진폭 × P ÷ 2π)."""
    rng = np.random.default_rng(spec.seed)
    t0 = spec.handling_s + spec.still_s
    duration = t0 + spec.swing_s + spec.still_s + spec.handling_s
    dt = 1.0 / spec.fs_hz
    t = 0.058 + np.arange(int((duration - 0.058) / dt)) * dt
    tau = t - t0
    on = (tau >= 0) & (tau <= spec.swing_s)
    w = np.where(on, spec.omega_amp_rad_s * np.exp(-spec.decay_per_s * tau) * np.sin(2 * np.pi * tau / spec.period_s),
                 0.0)
    axis = np.asarray(spec.axis, float) / np.linalg.norm(spec.axis)
    gyro = np.outer(w, axis) + spec.noise_rad_s * rng.standard_normal((len(t), 3))
    hand = (t < spec.handling_s) | (t > duration - spec.handling_s)
    gyro[hand] += spec.handling_rad_s * rng.standard_normal((int(hand.sum()), 3))
    amp_mid = spec.omega_amp_rad_s * np.exp(-spec.decay_per_s * spec.swing_s / 2) * spec.period_s / (2 * np.pi)
    truth = dict(period_s=spec.period_s, amp_deg=float(np.degrees(amp_mid)), swing_t0_s=t0,
                 swing_t1_s=t0 + spec.swing_s)
    return t, gyro, truth


# --- 수직 점프 (SPEC §10: 알려진 체공 시간·이륙 속도의 합성 가속도) ---


@dataclass
class JumpSpec:
    """합성 점프 기록 하나(허리 파우치). 몸 중심 수직 가속도를 구간마다 식으로 만든다(시간 s, 가속도 m/s²).

    반동(unweight_s 동안 −unweight_ms2 sin) → 밀기(push_s, 끝에서 지면반력 0) → 체공(flight) → 착지(land_s).
    밀기의 크기는 이륙 속도 g t_f ÷ 2가 되도록 정한다.
    """

    flight_times_s: tuple[float, ...] = (0.50, 0.46, 0.52)
    unweight_s: float = 0.35
    unweight_ms2: float = 6.0
    push_s: float = 0.40
    land_s: float = 0.25
    quiet_s: float = 2.0
    rest_s: float = 15.0
    handling_s: float = 3.0
    noise_g: float = 0.01
    orientation: str = "landscape"
    fs_hz: float = 99.58
    epoch_ms: int = 1_800_000_000_000
    seed: int = 0


def _jump_accel(tau: np.ndarray, spec: JumpSpec, flight_s: float) -> np.ndarray:
    """점프 하나의 몸 중심 수직 가속도(m/s²). tau = 반동 시작부터의 시간."""
    g = G0
    t1, t2, t3 = spec.unweight_s, spec.push_s, spec.land_s
    v_to = g * flight_s / 2
    a1 = spec.unweight_ms2
    a2 = (v_to + 2 * a1 * t1 / np.pi + g * t2 / 5) * np.pi / (2 * t2)
    a3 = (v_to + g * t3 / 2) * np.pi / (2 * t3)
    to, land = t1 + t2, t1 + t2 + flight_s
    a = np.zeros_like(tau)
    s = (tau >= 0) & (tau < t1)
    a[s] = -a1 * np.sin(np.pi * tau[s] / t1)
    s = (tau >= t1) & (tau < to)
    u = (tau[s] - t1) / t2
    a[s] = a2 * np.sin(np.pi * u) - g * u**4
    a[(tau >= to) & (tau < land)] = -g
    s = (tau >= land) & (tau < land + t3)
    u = (tau[s] - land) / t3
    a[s] = -g * (1 - (3 * u**2 - 2 * u**3)) + a3 * np.sin(np.pi * u)
    return a


def make_jump_imu(spec: JumpSpec, takeoff_level_g: float = 0.2, landing_level_g: float = 1.0
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict]]:
    """(t_s, 총 가속도 g N×3(몸 축: 앞뒤·좌우·위), Gravity N×3 m/s², 점프마다 정답).

    정답: takeoff_s, landing_s, flight_s, v_takeoff_ms, lowest_s(적분 속도가 0을 위로 지난 시각), pushoff_s, 그리고
    사건 정의(D-77)대로의 값: takeoff_evt_s(밀기 뒤 수직 비력이 takeoff_level_g(`flight.a_thresh_g`) 아래로 처음
    내려간 시각, 실제 이륙보다 몇 ms 앞),
    landing_evt_s(착지 뒤 수직 비력이 landing_level_g(`jump.landing_level_g`)를 처음 넘는 시각), flight_evt_s,
    v_evt_ms(이륙 사건 시각의 적분 속도), pushoff_evt_s.
    """
    rng = np.random.default_rng(spec.seed)
    one = spec.unweight_s + spec.push_s + max(spec.flight_times_s) + spec.land_s
    starts = [spec.handling_s + spec.quiet_s + k * (spec.quiet_s + one + spec.rest_s)
              for k in range(len(spec.flight_times_s))]
    duration = starts[-1] + one + spec.quiet_s + spec.handling_s
    dt = 1.0 / spec.fs_hz
    t = 0.058 + np.arange(int((duration - 0.058) / dt)) * dt
    a = np.zeros_like(t)
    truth = []
    fine = np.arange(0.0, one, 1e-4)
    for t0, tf in zip(starts, spec.flight_times_s, strict=True):
        a += _jump_accel(t - t0, spec, tf)
        af = _jump_accel(fine, spec, tf)
        v = np.cumsum(af) * 1e-4
        to = t0 + spec.unweight_s + spec.push_s
        up = np.where((v[:-1] <= 0) & (v[1:] > 0) & (fine[1:] < to - t0))[0]
        low = t0 + fine[up[-1] + 1]
        f = 1.0 + af / G0  # 사건 정의(SPEC §4.6, D-77)대로의 이륙·착지 시각과 그때의 속도
        i_to = int(np.flatnonzero((f <= takeoff_level_g) & (fine >= spec.unweight_s))[0])
        i_land = i_to + int(np.flatnonzero(f[i_to:] >= landing_level_g)[0])
        truth.append(dict(takeoff_s=to, landing_s=to + tf, flight_s=tf, v_takeoff_ms=G0 * tf / 2, lowest_s=low,
                          pushoff_s=to - low, takeoff_evt_s=t0 + fine[i_to], landing_evt_s=t0 + fine[i_land],
                          flight_evt_s=fine[i_land] - fine[i_to], v_evt_ms=float(v[i_to]),
                          pushoff_evt_s=t0 + fine[i_to] - low))
    up = 1.0 + a / G0
    hand = (t < spec.handling_s) | (t > duration - spec.handling_s)
    f_body = np.column_stack([np.zeros_like(t), np.zeros_like(t), up])
    f_body[hand] += 0.15 * rng.standard_normal((int(hand.sum()), 3))
    f_body += spec.noise_g * rng.standard_normal(f_body.shape)
    gravity = np.tile([0.0, 0.0, -G0], (len(t), 1))
    return t, f_body, gravity, truth


# --- 실험 2 시행 하나: 싱크 점프 3번 → 걷기 또는 달리기 (D-55) ---


@dataclass
class TrialSpec:
    """합성 실험 2 시행(허리 파우치). 달리기(run)면 걸음마다 접촉(반 사인파 지면반력)과 체공 flight_s가 번갈아 온다."""

    cadence_spm: float = 130.0
    n_steps: int = 60
    run: bool = False
    flight_s: float = 0.10
    amp_g: float = 0.5
    interval_cv_pct: float = 1.0
    sync_flight_s: float = 0.25
    n_sync: int = 3
    handling_s: float = 2.0
    stand_s: float = 3.0
    noise_g: float = 0.01
    fs_hz: float = 99.58
    epoch_ms: int = 1_800_000_000_000
    seed: int = 0


def make_trial_imu(spec: TrialSpec, takeoff_level_g: float = 0.2, landing_level_g: float = 1.0
                   ) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """(t_s, 총 가속도 g N×3(몸 축), Gravity N×3, 정답).

    정답: sync_takeoff_s·sync_landing_s(싱크 점프의 실제 이륙·닿은 시각들), sync_landing_evt_s(점프 사건 정의(D-77,
    D-80)대로의 착지: 착지 뒤 수직 비력이 landing_level_g를 처음 넘는 시각), step_times_s,
    flight_thr_s(달리기 체공을 0.2 g 문턱으로 잰 길이), contact_thr_s, cadence_spm.
    """
    rng = np.random.default_rng(spec.seed)
    hop = JumpSpec(unweight_s=0.25, unweight_ms2=4.0, push_s=0.30, land_s=0.20)
    hop_len = hop.unweight_s + hop.push_s + spec.sync_flight_s + hop.land_s
    hops = [spec.handling_s + spec.stand_s + k * (hop_len + 0.8) for k in range(spec.n_sync)]
    fine = np.arange(0.0, hop_len, 1e-4)
    fh = 1.0 + _jump_accel(fine, hop, spec.sync_flight_s) / G0
    i_to = int(np.flatnonzero((fh <= takeoff_level_g) & (fine >= hop.unweight_s))[0])
    i_land = i_to + int(np.flatnonzero(fh[i_to:] >= landing_level_g)[0])
    t_go = (hops[-1] + hop_len if hops else spec.handling_s) + spec.stand_s
    period = 60.0 / spec.cadence_spm
    steps = t_go + np.concatenate([[0.0], np.cumsum(period * (1 + spec.interval_cv_pct / 100
                                                              * rng.standard_normal(spec.n_steps - 1)))])
    duration = steps[-1] + period + spec.stand_s + spec.handling_s
    dt = 1.0 / spec.fs_hz
    t = 0.058 + np.arange(int((duration - 0.058) / dt)) * dt
    a = np.zeros_like(t)
    for h0 in hops:
        a += _jump_accel(t - h0, hop, spec.sync_flight_s)
    up = 1.0 + a / G0
    truth = dict(sync_takeoff_s=[h0 + hop.unweight_s + hop.push_s for h0 in hops],
                 sync_landing_s=[h0 + hop.unweight_s + hop.push_s + spec.sync_flight_s for h0 in hops],
                 sync_landing_evt_s=[h0 + fine[i_land] for h0 in hops],
                 cadence_spm=spec.cadence_spm, flight_thr_s=np.nan, contact_thr_s=np.nan)
    if spec.run:
        tc = period - spec.flight_s
        peak = np.pi / 2 * period / tc  # 접촉 중 반 사인파, 한 걸음 평균 1 g
        f_run = np.zeros_like(t)
        for s0 in steps:
            sel = (t >= s0) & (t < s0 + tc)
            f_run[sel] = peak * np.sin(np.pi * (t[sel] - s0) / tc)
        run_on = (t >= steps[0]) & (t < steps[-1] + tc)
        up[run_on] = f_run[run_on]
        off = tc / np.pi * np.arcsin(0.2 / peak)  # 접촉 시작·끝에서 0.2 g를 지나는 시각의 차이
        truth.update(step_times_s=steps + tc / 2, flight_thr_s=spec.flight_s + 2 * off, contact_thr_s=tc - 2 * off)
        ap_ml = np.zeros((len(t), 2))
    else:
        amps = spec.amp_g * (1 + 0.1 * rng.standard_normal(len(steps)))
        fb = _body_force(t, steps, amps, spec.cadence_spm)
        up += fb[:, 2]
        ap_ml = fb[:, :2]
        truth.update(step_times_s=steps)
    f_body = np.column_stack([ap_ml, up])
    hand = (t < spec.handling_s) | (t > duration - spec.handling_s)
    f_body[hand] += 0.15 * rng.standard_normal((int(hand.sum()), 3))
    f_body += spec.noise_g * rng.standard_normal(f_body.shape)
    return t, f_body, np.tile([0.0, 0.0, -G0], (len(t), 1)), truth


def write_imu_zip(path: str | Path, t: np.ndarray, f_body_g: np.ndarray, gyro: np.ndarray | None = None,
                  orientation: str = "landscape", epoch_ms: int = 1_800_000_000_000) -> None:
    """몸 축 비력(g)과 자이로(rad/s)를 Sensor Logger 형식 zip으로(위치·걸음 수 파일 없음, 실험 2·3용)."""
    rot = Rotation.from_matrix(FRAMES[orientation])
    f_dev = rot.apply(f_body_g)
    down = rot.apply(np.tile([0.0, 0.0, -1.0], (len(t), 1)))
    reading = -f_dev
    grav = G0 * down
    accel = G0 * reading - grav
    gyro = np.zeros((len(t), 3)) if gyro is None else gyro
    epoch_ns = epoch_ms * 10**6
    time_ns = epoch_ns + np.round(t * 1e9).astype("int64")

    def imu_csv(v: np.ndarray) -> bytes:
        df = pd.DataFrame({"time": time_ns, "seconds_elapsed": np.round(t, 6), "z": v[:, 2], "y": v[:, 1],
                           "x": v[:, 0]})
        return df.to_csv(index=False, float_format="%.9g", lineterminator="\n").encode()

    files = {"Accelerometer.csv": imu_csv(accel), "Gravity.csv": imu_csv(grav), "Gyroscope.csv": imu_csv(gyro),
             "AccelerometerUncalibrated.csv": imu_csv(reading), "GyroscopeUncalibrated.csv": imu_csv(gyro + 0.004)}
    rec_time = pd.Timestamp(epoch_ns, unit="ns", tz="UTC").strftime("%Y-%m-%d_%H-%M-%S")
    meta = pd.DataFrame([{"version": "3", "device name": "SYNTHETIC-DEVICE", "recording epoch time": epoch_ms,
                          "recording time": rec_time, "recording timezone": "Asia/Seoul", "platform": "ios",
                          "appVersion": "1.68.1", "device id": "00000000-SYNTH-0000",
                          "sensors": "Accelerometer|Gravity|Gyroscope|GyroscopeUncalibrated|AccelerometerUncalibrated",
                          "sampleRateMs": "10|10|10|10|10", "standardisation": "false",
                          "platform version": "26.2.1"}])
    files["Metadata.csv"] = meta.to_csv(index=False, lineterminator="\n").encode().rstrip(b"\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    Path(path).write_bytes(buf.getvalue())
