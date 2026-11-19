"""실험 3: 다리 진자 (SPEC §4.4, §5.8, DECISIONS D-06·D-24·D-41·D-58·D-73).

흔들림 주기 검출(시행 하나):
1. Gyroscope(rad/s)를 균일 격자로 옮기고, 주성분(첫 축) 각속도 ω(t)를 만든 뒤 저역 통과(`pendulum.gyro_lowpass_hz`).
2. 같은 방향(+) 봉우리: 간격 ≥ `pendulum.min_period_s`, 높이 ≥ max(`peak_height_frac` × √2 × 이동 RMS,
   `min_peak_rad_s`). 봉우리 시각은 포물선 보간으로 샘플 사이까지 잡는다(걸음 검출과 같다, D-48).
3. 간격이 [`min_period_s`, `max_period_s`] 안이고 사슬 중앙값의 ±`regular_tol_frac` 안인 가장 긴 사슬 = 흔들기.
4. 그 구간에서 주성분을 다시 구해 2–3을 한 번 더 한다(폰을 만진 움직임이 축을 흐리지 않게).
5. 처음과 마지막 한 주기를 빼고 간격의 중앙값 = P(굽힌 다리는 P_K). 사슬이 `min_cycles`(10)주기 미만이면 few_cycles.
6. 진폭: 남긴 구간의 ω를 적분한 각도(평균·선형 추세 제거)에서 주기마다 (최고 − 최저) ÷ 2, ω_peak는 주기마다
   (ω 최고 − ω 최저) ÷ 2. 둘 다 주기들의 중앙값(D-41).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

from walkmusic.config import Params

NAN = float("nan")


def _uniform(t: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    fs = 1.0 / float(np.median(np.diff(t)))
    n = int(np.floor((t[-1] - t[0]) * fs)) + 1
    tg = t[0] + np.arange(n) / fs
    return tg, np.column_stack([np.interp(tg, t, x[:, k]) for k in range(x.shape[1])]), fs


def _principal(x: np.ndarray) -> np.ndarray:
    _, _, vt = np.linalg.svd(x - x.mean(axis=0), full_matrices=False)
    return vt[0]


def _peaks(omega: np.ndarray, fs: float, params: Params) -> np.ndarray:
    k = max(1, int(round(params["pendulum.rms_window_s"] * fs)))
    rms = np.sqrt(np.convolve(omega**2, np.ones(k) / k, mode="same"))
    height = np.maximum(params["pendulum.peak_height_frac"] * np.sqrt(2.0) * rms, params["pendulum.min_peak_rad_s"])
    pk, _ = find_peaks(omega, height=height, distance=max(1, int(round(params["pendulum.min_period_s"] * fs))))
    return pk


def _longest_chain(tp: np.ndarray, params: Params) -> tuple[int, int] | None:
    """간격이 범위 안이고 고른 가장 긴 봉우리 사슬의 (첫 봉우리, 마지막 봉우리) 번호. 간격 3개 미만이면 None."""
    iv = np.diff(tp)
    ok = (iv >= params["pendulum.min_period_s"]) & (iv <= params["pendulum.max_period_s"])
    best, i = None, 0
    while i < len(iv):
        if not ok[i]:
            i += 1
            continue
        j = i
        while j < len(iv) and ok[j]:
            j += 1
        seg = iv[i:j]
        bad = np.where(np.abs(seg / np.median(seg) - 1) > params["pendulum.regular_tol_frac"])[0]
        edges = np.r_[-1, bad, len(seg)]
        for a, b in zip(edges[:-1] + 1, edges[1:], strict=True):  # 고르지 않은 간격에서 자른 조각 [a, b)
            if b - a >= 3 and (best is None or b - a > best[1] - best[0]):
                best = (i + a, i + b)
        i = j
    return best


def _swing(tg: np.ndarray, x: np.ndarray, fs: float, params: Params, span: tuple[float, float] | None):
    sel = np.ones(len(tg), bool) if span is None else (tg >= span[0]) & (tg <= span[1])
    axis = _principal(x[sel])
    sos = butter(params["pendulum.filter_order"], params["pendulum.gyro_lowpass_hz"], btype="lowpass", fs=fs,
                 output="sos")
    omega = sosfiltfilt(sos, x @ axis)
    pk = _peaks(omega, fs, params)
    if span is not None:
        pk = pk[(tg[pk] >= span[0] - 1e-9) & (tg[pk] <= span[1] + 1e-9)]
    chain = _longest_chain(_peak_times(tg, omega, pk, fs), params)
    return omega, pk, chain


def _peak_times(tg: np.ndarray, omega: np.ndarray, pk: np.ndarray, fs: float) -> np.ndarray:
    """봉우리 시각을 포물선 보간으로 샘플 사이까지(걸음 검출과 같은 방법, D-48)."""
    inner = (pk > 0) & (pk < len(omega) - 1)
    out = tg[pk].astype(float)
    k = pk[inner]
    a, b, c = omega[k - 1], omega[k], omega[k + 1]
    den = a - 2 * b + c
    out[inner] += np.where(den != 0, 0.5 * (a - c) / np.where(den != 0, den, 1), 0.0) / fs
    return out


def analyze_gyro(t: np.ndarray, gyro: np.ndarray, params: Params) -> dict:
    """정강이 Gyroscope(t_s, N×3 rad/s) → 흔들림 주기와 진폭(시행 하나).

    돌려주는 값: swing_period_s, n_cycles(중앙값에 쓴 주기 수), n_cycles_total(이어진 흔들림 전체),
    amp_deg, omega_peak_rad_s, swing_t0_s, swing_t1_s, flags(list).
    """
    out = dict(swing_period_s=NAN, n_cycles=0, n_cycles_total=0, amp_deg=NAN, omega_peak_rad_s=NAN,
               swing_t0_s=NAN, swing_t1_s=NAN, flags=[])
    if len(t) < 10:
        out["flags"].append("no_swing")
        return out
    tg, x, fs = _uniform(np.asarray(t, float), np.asarray(gyro, float))
    omega, pk, chain = _swing(tg, x, fs, params, None)
    if chain is not None:  # 흔들기 구간에서 축을 다시 구한다
        refined = _swing(tg, x, fs, params, (tg[pk[chain[0]]] - 0.5 / fs, tg[pk[chain[1]]] + 0.5 / fs))
        if refined[2] is not None:
            omega, pk, chain = refined
    if chain is None:
        out["flags"].append("no_swing")
        return out
    tp = _peak_times(tg, omega, pk, fs)[chain[0]:chain[1] + 1]
    iv = np.diff(tp)
    kept = iv[1:-1]
    out.update(swing_period_s=float(np.median(kept)), n_cycles=len(kept), n_cycles_total=len(iv),
               swing_t0_s=float(tp[0]), swing_t1_s=float(tp[-1]))
    if len(iv) < params["pendulum.min_cycles"]:
        out["flags"].append("few_cycles")
    gaps = np.diff(np.asarray(t, float))
    inside = (np.asarray(t, float)[:-1] >= tp[0]) & (np.asarray(t, float)[1:] <= tp[-1])
    if (gaps[inside] > params["qa.gap_fail_s"]).any():
        out["flags"].append("sensor_gap")

    a, b = np.searchsorted(tg, tp[1]), np.searchsorted(tg, tp[-2])  # 처음·마지막 주기를 뺀 구간
    w = omega[a:b + 1] - omega[a:b + 1].mean()
    theta = np.concatenate([[0.0], np.cumsum((w[1:] + w[:-1]) / 2) / fs])
    idx = np.arange(len(theta))
    theta -= np.polyval(np.polyfit(idx, theta, 1), idx)
    edges = np.searchsorted(tg[a:b + 1], tp[1:-1])
    amps, peaks = [], []
    for c0, c1 in zip(edges[:-1], edges[1:], strict=True):
        if c1 > c0:
            amps.append((theta[c0:c1 + 1].max() - theta[c0:c1 + 1].min()) / 2)
            peaks.append((omega[a + c0:a + c1 + 1].max() - omega[a + c0:a + c1 + 1].min()) / 2)
    if amps:
        out.update(amp_deg=float(np.degrees(np.median(amps))), omega_peak_rad_s=float(np.median(peaks)))
    return out
