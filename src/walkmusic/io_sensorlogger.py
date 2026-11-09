"""Sensor Logger zip 읽기와 시간축 (SPEC §3.1, §5.1, DECISIONS D-27·D-43·D-47).

- zip은 풀지 않고 읽는다. 열은 이름으로 읽는다(실제 파일은 z, y, x 순서).
- 시간축 t_s = (time − 기록 시작) ÷ 1e9. 기록 시작은 Metadata의 recording epoch time,
  없으면 IMU 파일 첫 time의 최솟값(Location·Pedometer 제외, D-43).
- Metadata의 device name·device id는 읽자마자 버린다. 좌표 값은 반환 객체에 남지만 출력하지 않는다.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from walkmusic.config import Params, load_params

IMU = ("Accelerometer", "AccelerometerUncalibrated", "Gravity", "Gyroscope", "GyroscopeUncalibrated")
IMU_EPOCH = ("Accelerometer", "Gravity", "Gyroscope")
KNOWN = (*IMU, "Location", "Pedometer", "Metadata", "Annotation")
SAFE_META = ("version", "recording epoch time", "recording time", "recording timezone", "platform", "appVersion",
             "sensors", "sampleRateMs", "standardisation", "platform version")
COORD_COLUMNS = ("latitude", "longitude")


@dataclass
class Recording:
    """zip 하나. sensors의 각 표는 t_s(s) 열과 값 열(time·seconds_elapsed 제외)을 가진다."""

    source: str
    epoch_ns: int
    epoch_source: str
    timezone: str
    meta: dict[str, str]
    files: dict[str, int]
    sensors: dict[str, pd.DataFrame]
    empty: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)

    def kst(self, t_s: float) -> pd.Timestamp:
        """t_s(기록 시작 후 초)를 현지 시각(time.timezone)으로."""
        return pd.Timestamp(self.epoch_ns + int(round(t_s * 1e9)), unit="ns", tz="UTC").tz_convert(self.timezone)

    def has(self, name: str) -> bool:
        """센서 표가 있고 행이 하나 이상인가."""
        return name in self.sensors and len(self.sensors[name]) > 0

    def xyz(self, name: str) -> np.ndarray:
        """IMU 표의 (x, y, z) 배열 (N×3)."""
        return self.sensors[name][["x", "y", "z"]].to_numpy(float)

    def t(self, name: str) -> np.ndarray:
        """센서 표의 t_s 배열."""
        return self.sensors[name]["t_s"].to_numpy(float)


def _epoch_from_meta(meta: dict[str, str]) -> int | None:
    raw = meta.get("recording epoch time", "").strip()
    if not raw:
        return None
    v = int(float(raw))
    scale = {10: 10**9, 13: 10**6, 16: 10**3, 19: 1}.get(len(str(abs(v))))
    return None if scale is None else v * scale


def read_zip(path: str | Path, params: Params | None = None) -> Recording:
    """Sensor Logger zip을 읽어 :class:`Recording`으로 돌려준다."""
    params = params or load_params()
    path = Path(path)
    files: dict[str, int] = {}
    raw: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = Path(info.filename).name
            if info.is_dir() or not name:
                continue
            files[name] = info.file_size
            if name.endswith(".csv"):
                raw[name[:-4]] = z.read(info)
    empty = sorted(s for s, b in raw.items() if not b.strip())
    unknown = sorted(s for s in raw if s not in KNOWN)

    meta: dict[str, str] = {}
    if "Metadata" in raw and raw["Metadata"].strip():
        mdf = pd.read_csv(io.BytesIO(raw["Metadata"]), dtype=str, keep_default_na=False)
        if len(mdf):
            row = mdf.iloc[0]
            meta = {k: str(row[k]) for k in SAFE_META if k in mdf.columns}  # 기기 이름·ID는 남기지 않는다

    tables: dict[str, pd.DataFrame] = {}
    for name in (*IMU, "Location", "Pedometer"):
        if name in raw and name not in empty:
            df = pd.read_csv(io.BytesIO(raw[name]))
            if len(df) == 0:
                empty.append(name)
                continue
            tables[name] = df

    epoch = _epoch_from_meta(meta)
    source = "metadata"
    if epoch is None:
        firsts = [int(tables[n]["time"].min()) for n in IMU_EPOCH if n in tables]
        if not firsts:
            raise ValueError(f"{path.name}: 기록 시작 시각을 정할 수 없다(Metadata·IMU 없음)")
        epoch, source = min(firsts), "imu_first"

    sensors: dict[str, pd.DataFrame] = {}
    dropped: dict[str, int] = {}
    for name, df in tables.items():
        df = df.sort_values("time", kind="stable")
        out = df.drop(columns=[c for c in ("time", "seconds_elapsed") if c in df.columns])
        out.insert(0, "t_s", (df["time"].to_numpy("int64") - epoch) / 1e9)
        if name == "Location":
            keep = out["t_s"].to_numpy() >= 0  # 기록 전 위치 점은 버린다(D-43)
            dropped[name] = int((~keep).sum())
            out = out[keep].copy()
            for c in ("speed", "speedAccuracy"):
                if c in out.columns:
                    out.loc[out[c] < 0, c] = np.nan  # −1은 무효 값
        sensors[name] = out.reset_index(drop=True)
    return Recording(source=path.name, epoch_ns=int(epoch), epoch_source=source, timezone=params["time.timezone"],
                     meta=meta, files=files, sensors=sensors, empty=sorted(empty), unknown=unknown, dropped=dropped)


def interval_stats(t_s: np.ndarray, gap_warn_s: float, gap_fail_s: float) -> dict:
    """샘플 간격 요약: 중앙(ms), fs(Hz), p5·p95(ms), 최대(s), 문턱 넘는 끊김 목록 [(t_s, 길이 s)]."""
    dt = np.diff(np.asarray(t_s, dtype=float))
    if len(dt) == 0:
        return dict(n=len(t_s))
    med = float(np.median(dt))
    big = np.where(dt > gap_warn_s)[0]
    return dict(n=len(t_s), median_ms=med * 1000, fs_hz=1 / med, p5_ms=float(np.percentile(dt, 5)) * 1000,
                p95_ms=float(np.percentile(dt, 95)) * 1000, max_s=float(dt.max()),
                n_gt_warn=int(len(big)), n_gt_fail=int((dt > gap_fail_s).sum()),
                gaps=[(float(t_s[i]), float(dt[i])) for i in big])


def uniform_segments(t_s: np.ndarray, values: np.ndarray, max_gap_s: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """중앙 간격의 균일 격자로 선형 보간한다. max_gap_s보다 긴 끊김은 가로지르지 않고 조각을 나눈다(SPEC §5.1).

    values는 (N,) 또는 (N, k). 각 조각의 (t 격자, 보간 값)을 돌려준다.
    """
    t = np.asarray(t_s, dtype=float)
    v = np.asarray(values, dtype=float)
    dt = float(np.median(np.diff(t)))
    cuts = np.where(np.diff(t) > max_gap_s)[0] + 1
    out = []
    for a, b in zip(np.r_[0, cuts], np.r_[cuts, len(t)], strict=True):
        if b - a < 2:
            continue
        grid = np.arange(t[a], t[b - 1] + dt / 2, dt)
        if v.ndim == 1:
            out.append((grid, np.interp(grid, t[a:b], v[a:b])))
        else:
            out.append((grid, np.column_stack([np.interp(grid, t[a:b], v[a:b, j]) for j in range(v.shape[1])])))
    return out


def inspect_report(rec: Recording, params: Params | None = None) -> str:
    """파일 구조와 시간·샘플링 요약 문자열(좌표 값·기기 이름 없음)."""
    params = params or load_params()
    warn, fail = params["qa.gap_warn_s"], params["qa.gap_fail_s"]
    fmt = "%Y-%m-%d %H:%M:%S.%f"
    lines = [f"# inspect {rec.source}", "",
             f"기록 시작: {rec.kst(0).strftime(fmt)[:-3]} ({rec.timezone}) = t_s 0  [{rec.epoch_source}]"]
    if "Accelerometer" in rec.sensors:
        ta = rec.t("Accelerometer")
        lines.append(f"기록 길이(Accelerometer 첫~끝): {ta[-1] - ta[0]:.1f} s")
    lines += ["", "## zip 안 파일", "파일 | 바이트 | 행 | 열"]
    for name, size in sorted(rec.files.items()):
        stem = name[:-4] if name.endswith(".csv") else name
        df = rec.sensors.get(stem)
        cols = ", ".join(df.columns[1:]) if df is not None else ""
        rows = len(df) if df is not None else ("비어 있음" if stem in rec.empty else "-")
        lines.append(f"{name} | {size} | {rows} | {cols}")
    if rec.empty:
        lines.append(f"빈 파일: {', '.join(rec.empty)}")
    if rec.unknown:
        lines.append(f"모르는 파일: {', '.join(rec.unknown)}")
    lines += ["", f"## 센서별 시각과 샘플링 (끊김 문턱 {warn} s, {fail} s)",
              "센서 | 첫 시각 | 끝 시각 | 첫 t_s | 중앙 간격 ms | fs Hz | p5/p95 ms | 최대 s | >경고 | >실패"]
    for name, df in rec.sensors.items():
        t = df["t_s"].to_numpy(float)
        if len(t) < 2:
            continue
        if name in IMU:
            s = interval_stats(t, warn, fail)
        else:  # 저속 센서는 제 주기의 1.5배를 끊김으로 본다
            thr = max(1.0, 1.5 * float(np.median(np.diff(t))))
            s = interval_stats(t, thr, thr)
        lines.append(f"{name} | {rec.kst(t[0]).strftime(fmt)[11:-3]} | {rec.kst(t[-1]).strftime(fmt)[11:-3]} | "
                     f"{t[0]:.3f} | {s['median_ms']:.3f} | {s['fs_hz']:.2f} | {s['p5_ms']:.3f}/{s['p95_ms']:.3f} | "
                     f"{s['max_s']:.3f} | {s['n_gt_warn']} | {s['n_gt_fail']}")
        if name in IMU:
            for t0, d in s["gaps"][:10]:
                lines.append(f"  끊김 {d:.3f} s at t_s {t0:.2f}")
    if rec.dropped:
        lines.append(f"버린 행(기록 전 위치 점 등): {rec.dropped}")
    lines += ["", "## Metadata(안전한 항목만)"] + [f"{k}: {v}" for k, v in rec.meta.items()]
    if "Accelerometer" in rec.sensors:
        end = rec.t("Accelerometer")[-1]
        lines += ["", "## 시계 시각 ↔ t_s (기록지 메모를 exclusions.csv로 옮길 때)"]
        first = rec.kst(0).ceil("min")
        n_min = int(end // 60) + 1
        for k in range(n_min):
            ts = first + pd.Timedelta(minutes=k)
            t_s = (ts.value - rec.epoch_ns) / 1e9
            if t_s <= end:
                lines.append(f"{ts.strftime('%H:%M')} = t_s {t_s:.1f}")
    return "\n".join(lines)
