"""걸음 검출과 출발·도착 (SPEC §5.4, §5.5(a), DECISIONS D-02·D-09·D-21·D-33·D-36).

1. 신호: 총 가속도 크기(steps.signal = magnitude) 또는 수직 성분(vertical), 단위 g.
2. 끊김을 가로지르지 않는 균일 격자 → 영위상 대역 통과(steps.detect_band_hz).
3. 봉우리: 최소 간격 steps.min_interval_s, 높이 ≥ max(adaptive_k × 이동 RMS, floor_frac × 걷는 동안 RMS 중앙값).
   봉우리 시각은 포물선 보간으로 샘플 사이까지 잡는다.
4. 묶음: 간격 > exclude.stop_gap_s에서 나눈다. 걷기 묶음 = 걸음 exclude.min_bout_steps 이상,
   간격 CV ≤ steps.bout_max_cv_pct, 봉우리 높이 중앙값 ≥ steps.bout_min_height_frac × 가장 큰 묶음의 값.
5. 출발·도착(D-36): 기록 처음·끝 exclude.stand_search_s 안에서 1 s 움직임이 걷는 동안 중앙값의
   exclude.stand_min_s 이상 stand_motion_frac 미만인 구간(서 있기)을 찾고, 그 사이의 걷기 걸음만 쓴다.
   서 있기가 없으면 첫·마지막 걷기 묶음(D-21)으로 정하고 flags에 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

from walkmusic.config import Params
from walkmusic.io_sensorlogger import Recording, uniform_segments
from walkmusic.orientation import unit_rows, vertical_signal
from walkmusic.units import Units, determine_units, total_accel_g


@dataclass
class StepResult:
    """걸음 검출 결과. 시각은 모두 t_s(기록 시작 후 s)."""

    signal: str
    t_s: np.ndarray
    height_g: np.ndarray
    bouts: list[tuple[float, float, int]]
    rejected: list[tuple[float, float, int, str]]
    stand_start: tuple[float, float] | None
    stand_end: tuple[float, float] | None
    t_depart: float
    t_arrive: float
    flags: list[str] = field(default_factory=list)

    def window_steps(self, a: float | None = None, b: float | None = None) -> np.ndarray:
        """[a, b] 안의 걸음 시각. 기본은 [t_depart, t_arrive]."""
        a = self.t_depart if a is None else a
        b = self.t_arrive if b is None else b
        return self.t_s[(self.t_s >= a - 1e-9) & (self.t_s <= b + 1e-9)]

    def intervals(self, a: float | None = None, b: float | None = None, stop_gap_s: float = 2.0) -> np.ndarray:
        """창 안 걸음 간격(s). 정지(stop_gap_s 초과)를 가로지르는 간격은 뺀다."""
        iv = np.diff(self.window_steps(a, b))
        return iv[iv <= stop_gap_s]


def motion_per_second(t: np.ndarray, total_g: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """1 s 창마다 움직임 지표 √(세 축 분산 합) (g). (창 시작 초, 값)."""
    sec = np.floor(t).astype(int)
    starts, vals = [], []
    for s in np.unique(sec):
        m = sec == s
        if m.sum() >= 10:
            starts.append(s)
            vals.append(float(np.sqrt(total_g[m].var(axis=0).sum())))
    return np.asarray(starts, float), np.asarray(vals)


def _signal(total_g: np.ndarray, gravity: np.ndarray, kind: str) -> np.ndarray:
    if kind == "magnitude":
        return np.linalg.norm(total_g, axis=1)
    if kind == "vertical":
        return vertical_signal(total_g, gravity)
    raise ValueError(f"steps.signal은 magnitude 또는 vertical: {kind}")


def _peaks(t: np.ndarray, sig: np.ndarray, params: Params, walk_sec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = params["steps.detect_band_hz"]
    segs = []
    for tg, x in uniform_segments(t, sig, params["qa.gap_warn_s"]):
        fs = 1.0 / float(np.median(np.diff(tg)))
        if tg[-1] - tg[0] < 3.0:
            continue
        sos = butter(params["steps.filter_order"], [lo, hi], btype="bandpass", fs=fs, output="sos")
        y = sosfiltfilt(sos, x - x.mean())
        k = max(1, int(round(params["steps.adaptive_window_s"] * fs)))
        rms = np.sqrt(np.convolve(y**2, np.ones(k) / k, mode="same"))
        segs.append((tg, y, rms, fs))
    if not segs:
        return np.array([]), np.array([])
    walk_rms = np.concatenate([rms[np.isin(np.floor(tg), walk_sec)] for tg, _, rms, _ in segs])
    all_rms = np.concatenate([rms for _, _, rms, _ in segs])
    floor = params["steps.floor_frac"] * float(np.median(walk_rms if len(walk_rms) else all_rms))
    times, heights = [], []
    for tg, y, rms, fs in segs:
        pk, pr = find_peaks(y, height=np.maximum(params["steps.adaptive_k"] * rms, floor),
                            distance=max(1, int(round(params["steps.min_interval_s"] * fs))))
        pk = pk[(pk > 0) & (pk < len(y) - 1)]
        a, b, c = y[pk - 1], y[pk], y[pk + 1]
        den = a - 2 * b + c
        off = np.where(den != 0, 0.5 * (a - c) / np.where(den != 0, den, 1), 0.0)
        times.append(tg[pk] + off / fs)
        heights.append(b)
    return np.concatenate(times), np.concatenate(heights)


def _runs(mask_sec: np.ndarray, secs: np.ndarray, min_len: float) -> list[tuple[float, float]]:
    """연속된 '가만히' 초의 구간 [시작, 끝) 중 min_len 이상."""
    out, i = [], 0
    while i < len(secs):
        if mask_sec[i]:
            j = i
            while j + 1 < len(secs) and mask_sec[j + 1] and secs[j + 1] == secs[j] + 1:
                j += 1
            if secs[j] + 1 - secs[i] >= min_len:
                out.append((float(secs[i]), float(secs[j] + 1)))
            i = j + 1
        else:
            i += 1
    return out


def detect_steps(t: np.ndarray, total_g: np.ndarray, gravity: np.ndarray, params: Params,
                 signal: str | None = None) -> StepResult:
    """총 가속도(g)에서 걸음과 출발·도착을 찾는다. gravity는 수직 방향용(원래 단위)."""
    kind = signal or params["steps.signal"]
    secs, motion = motion_per_second(t, total_g)
    ref = float(np.median(motion[motion >= np.median(motion)])) if len(motion) else 0.0
    walk_sec = secs[motion > params["steps.motion_walk_frac"] * ref]
    st, h = _peaks(t, _signal(total_g, gravity, kind), params, walk_sec)

    # 묶음과 걷기 판정
    order = np.argsort(st)
    st, h = st[order], h[order]
    cuts = np.where(np.diff(st) > params["exclude.stop_gap_s"])[0] + 1
    coarse = [(a, b) for a, b in zip(np.r_[0, cuts], np.r_[cuts, len(st)], strict=True) if b > a]
    groups = []  # 묶음 안에서 간격이 중앙값과 bout_split_frac 넘게 다른 곳(흔들림·누락)을 다시 자른다
    for a, b in coarse:
        iv = np.diff(st[a:b])
        if len(iv) < 2:
            groups.append((a, b))
            continue
        odd = np.abs(iv / np.median(iv) - 1) > params["steps.bout_split_frac"]
        sub = np.where(odd)[0] + 1 + a
        groups += [(x, y) for x, y in zip(np.r_[a, sub], np.r_[sub, b], strict=True) if y > x]
    big = max(groups, key=lambda ab: ab[1] - ab[0]) if groups else None
    ref_h = float(np.median(h[big[0]:big[1]])) if big else 0.0
    keep = np.zeros(len(st), bool)
    bouts, rejected = [], []
    for a, b in groups:
        n = b - a
        iv = np.diff(st[a:b])
        cv = float(iv.std(ddof=1) / iv.mean() * 100) if n > 2 else float("inf")
        why = ("few_steps" if n < params["exclude.min_bout_steps"] else
               "irregular" if cv > params["steps.bout_max_cv_pct"] else
               "low_height" if np.median(h[a:b]) < params["steps.bout_min_height_frac"] * ref_h else "")
        if why:
            rejected.append((float(st[a]), float(st[b - 1]), n, why))
        else:
            keep[a:b] = True
            bouts.append((float(st[a]), float(st[b - 1]), n))
    st, h = st[keep], h[keep]
    flags: list[str] = []
    if not bouts:
        return StepResult(kind, st, h, bouts, rejected, None, None, float("nan"), float("nan"), ["no_walking"])

    # 서 있기와 출발·도착(D-36)
    in_walk = np.zeros(len(secs), bool)
    for a, b, _ in bouts:
        in_walk |= (secs >= np.floor(a)) & (secs < b)
    still = motion < params["exclude.stand_motion_frac"] * float(np.median(motion[in_walk]))
    runs = _runs(still, secs, params["exclude.stand_min_s"])
    search = params["exclude.stand_search_s"]
    main = max(bouts, key=lambda x: x[2])
    t_end = float(t[-1])
    starts = [r for r in runs if r[0] < t[0] + search and r[1] <= main[0] + 1.0]
    ends = [r for r in runs if r[1] > t_end - search and r[0] >= main[1] - 1.0]
    stand_start = max(starts, key=lambda r: r[1]) if starts else None
    stand_end = min(ends, key=lambda r: r[0]) if ends else None
    if stand_start:
        after = st[st >= stand_start[1] - 1.0]
        t_dep = float(after[0]) if len(after) else float(bouts[0][0])
    else:
        t_dep = bouts[0][0]
        flags.append("no_start_standing")
    if stand_end:
        before = st[st <= stand_end[0] + 1.0]
        t_arr = float(before[-1]) if len(before) else float(bouts[-1][1])
    else:
        t_arr = bouts[-1][1]
        flags.append("no_end_standing")
    return StepResult(kind, st, h, bouts, rejected, stand_start, stand_end, t_dep, t_arr, flags)


def analyze_recording(rec: Recording, params: Params, signal: str | None = None,
                      units: Units | None = None) -> tuple[Units, StepResult]:
    """Recording → (단위 판별, 걸음 검출)."""
    units = units or determine_units(rec)
    t, total, g = total_accel_g(rec, units)
    return units, detect_steps(t, total, g, params, signal)


def cadence_summary(res: StepResult, params: Params, a: float | None = None, b: float | None = None) -> dict:
    """창 안 걸음 수, 케이던스 중앙(60/유효 간격)·rate, CV(%), 이상 간격 비율."""
    iv = res.intervals(a, b, params["exclude.stop_gap_s"])
    lo, hi = params["steps.min_interval_s"], params["steps.max_interval_s"]
    ok = iv[(iv >= lo) & (iv <= hi)]
    n_steps = len(res.window_steps(a, b))
    if len(ok) < 2:
        return dict(n_steps=n_steps, n_intervals=len(iv), bad_frac=float("nan"), cadence_median_spm=float("nan"),
                    cadence_rate_spm=float("nan"), cv_pct=float("nan"))
    return dict(n_steps=n_steps, n_intervals=len(iv), bad_frac=1 - len(ok) / len(iv),
                cadence_median_spm=float(np.median(60 / ok)), cadence_rate_spm=float(len(ok) / ok.sum() * 60),
                cv_pct=float(ok.std(ddof=params["stats.sd_ddof"]) / ok.mean() * 100))


def ml_dominant_hz(t: np.ndarray, total_g: np.ndarray, gravity: np.ndarray, a: float, b: float) -> float:
    """[a, b]에서 좌우(ML) 축 스펙트럼의 주 주파수(Hz). 수평면 PCA의 둘째 축(첫째는 AP, SPEC §5.3)."""
    sel = (t >= a) & (t <= b)
    tt, x, g = t[sel], total_g[sel], gravity[sel]
    u = unit_rows(g)
    horiz = x - np.einsum("ij,ij->i", x, u)[:, None] * u
    horiz -= horiz.mean(axis=0)
    _, _, vt = np.linalg.svd(horiz, full_matrices=False)
    ml = horiz @ vt[1]
    fs = 1.0 / float(np.median(np.diff(tt)))
    grid = np.arange(tt[0], tt[-1], 1 / fs)
    sig = np.interp(grid, tt, ml)
    spec = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    f = np.fft.rfftfreq(len(sig), 1 / fs)
    band = (f > 0.3) & (f < 3.0)
    return float(f[band][np.argmax(spec[band])])
