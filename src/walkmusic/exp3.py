"""실험 3: 다리 진자 (SPEC §4.4, §5.8, DECISIONS D-06·D-24·D-41·D-58·D-73).

흔들림 주기 검출(시행 하나):
1. Gyroscope(rad/s)를 균일 격자로 옮기고, 주성분(첫 축) 각속도 ω(t)를 만든 뒤 저역 통과(`pendulum.gyro_lowpass_hz`).
   첫 축 후보는 기록 전체의 주성분과, 회전이 한 평면에 가장 잘 모인 2 × `max_period_s` 창들의 주성분이고,
   가장 긴 사슬(3)을 주는 축을 쓴다(폰을 만지는 큰 움직임이 전체 주성분을 흐릴 때를 위해).
2. 같은 방향(+) 봉우리: 간격 ≥ `pendulum.min_period_s`, 높이 ≥ max(`peak_height_frac` × √2 × 이동 RMS,
   `min_peak_rad_s`). 봉우리 시각은 포물선 보간으로 샘플 사이까지 잡는다(걸음 검출과 같다, D-48).
3. 간격이 [`min_period_s`, `max_period_s`] 안이고 사슬 중앙값의 ±`regular_tol_frac` 안인 가장 긴 사슬 = 흔들기.
4. 그 구간에서 주성분을 다시 구해 2–3을 한 번 더 한다(폰을 만진 움직임이 축을 흐리지 않게).
   다시 구한 축의 부호는 처음 축에 맞춘다. 가속도가 있으면 걸을 때 발 닿음 근처 봉우리는 뺀다(`walk_impact_g`).
5. 처음과 마지막 한 주기를 빼고 간격의 중앙값 = P(굽힌 다리는 P_K). 사슬이 `min_cycles`(10)주기 미만이면 few_cycles.
   같은 방향 봉우리로 세면 시작·끝 위상에 따라 주기 수가 하나 다를 수 있어 +·− 방향 중 긴 사슬을 쓴다.
   흔들기 밖에 주기가 다른 고른 리듬(`min_cycles` ÷ 2 이상)이 있으면 other_rhythm(사람이 확인).
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
    k = min(max(1, int(round(params["pendulum.rms_window_s"] * fs))), len(omega))  # 짧은 기록도 길이를 맞춘다
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


def _candidate_axes(x: np.ndarray, fs: float, params: Params, n_best: int = 5) -> list[np.ndarray]:
    """첫 축 후보: 기록 전체의 주성분과, 2 × `max_period_s` 창 가운데 회전이 한 평면에 가장 잘 모인(첫 성분 비율이 큰)
    창들의 주성분. 폰을 만지는 큰 움직임(세 축으로 흩어진다)이 기록 전체의 주성분을 흐려도 흔들기 축이 후보에 든다."""
    axes = [_principal(x)]
    win = int(round(2 * params["pendulum.max_period_s"] * fs))
    if len(x) <= win:
        return axes
    scored = []
    for a in range(0, len(x) - win + 1, max(1, win // 4)):
        seg = x[a:a + win] - x[a:a + win].mean(axis=0)
        _, sv, vt = np.linalg.svd(seg, full_matrices=False)
        if sv[0] / np.sqrt(win) * np.sqrt(2.0) >= params["pendulum.min_peak_rad_s"]:  # 가만히 있는 창은 뺀다
            scored.append((float(sv[0] ** 2 / (sv**2).sum()), vt[0]))
    scored.sort(key=lambda s: -s[0])
    return axes + [v for _, v in scored[:n_best]]


def _swing(tg: np.ndarray, x: np.ndarray, fs: float, params: Params, span: tuple[float, float] | None,
           ref_axis: np.ndarray | None = None, impacts: np.ndarray | None = None, axis: np.ndarray | None = None):
    """축(주지 않으면 span 안 주성분)으로 ω를 만들고 봉우리 사슬을 찾는다. ref_axis와 같은 방향으로 부호를 맞춘다."""
    sel = np.ones(len(tg), bool) if span is None else (tg >= span[0]) & (tg <= span[1])
    if axis is None:
        axis = _principal(x[sel])
    if ref_axis is not None and float(axis @ ref_axis) < 0:
        axis = -axis
    sos = butter(params["pendulum.filter_order"], params["pendulum.gyro_lowpass_hz"], btype="lowpass", fs=fs,
                 output="sos")
    omega = sosfiltfilt(sos, x @ axis)
    pk, chain = _chain(tg, omega, fs, params, span, impacts)
    return omega, pk, chain, axis


def _chain(tg: np.ndarray, omega: np.ndarray, fs: float, params: Params, span: tuple[float, float] | None,
           impacts: np.ndarray | None):
    """ω의 + 봉우리(span 안, 발 닿음 근처 제외)와 그 가장 긴 고른 사슬."""
    pk = _peaks(omega, fs, params)
    if span is not None:
        pk = pk[(tg[pk] >= span[0] - 1e-9) & (tg[pk] <= span[1] + 1e-9)]
    if impacts is not None and len(impacts) and len(pk):
        if len(impacts) > 1:
            j = np.clip(np.searchsorted(impacts, tg[pk]), 1, len(impacts) - 1)
        else:
            j = np.zeros(len(pk), int)
        near = np.minimum(np.abs(tg[pk] - impacts[j]), np.abs(tg[pk] - impacts[np.maximum(j - 1, 0)]))
        pk = pk[near > params["pendulum.min_period_s"]]
    return pk, _longest_chain(_peak_times(tg, omega, pk, fs), params)


def _peak_times(tg: np.ndarray, omega: np.ndarray, pk: np.ndarray, fs: float) -> np.ndarray:
    """봉우리 시각을 포물선 보간으로 샘플 사이까지(걸음 검출과 같은 방법, D-48)."""
    inner = (pk > 0) & (pk < len(omega) - 1)
    out = tg[pk].astype(float)
    k = pk[inner]
    a, b, c = omega[k - 1], omega[k], omega[k + 1]
    den = a - 2 * b + c
    out[inner] += np.where(den != 0, 0.5 * (a - c) / np.where(den != 0, den, 1), 0.0) / fs
    return out


def analyze_gyro(t: np.ndarray, gyro: np.ndarray, params: Params, acc_t: np.ndarray | None = None,
                 acc_mag_g: np.ndarray | None = None) -> dict:
    """정강이 Gyroscope(t_s, N×3 rad/s) → 흔들림 주기와 진폭(시행 하나).

    acc_t·acc_mag_g(총 가속도 크기, g)가 있으면 크기가 `pendulum.walk_impact_g` 이상인 시각(걸을 때 발 닿음)에서
    `pendulum.min_period_s` 안의 봉우리를 뺀다. 계단까지 걸어간 구간의 보폭 리듬을 흔들기로 잡지 않게 한다.
    돌려주는 값: swing_period_s, n_cycles(중앙값에 쓴 주기 수), n_cycles_total(이어진 흔들림 전체),
    amp_deg, omega_peak_rad_s, swing_t0_s, swing_t1_s, flags(list).
    """
    out = dict(swing_period_s=NAN, n_cycles=0, n_cycles_total=0, amp_deg=NAN, omega_peak_rad_s=NAN,
               swing_t0_s=NAN, swing_t1_s=NAN, flags=[])
    t = np.asarray(t, float)
    if len(t) < 10 or t[-1] - t[0] < 3 * params["pendulum.min_period_s"]:
        out["flags"].append("no_swing")
        return out
    impacts = None
    if acc_t is not None and acc_mag_g is not None:
        impacts = np.sort(np.asarray(acc_t, float)[np.asarray(acc_mag_g, float) >= params["pendulum.walk_impact_g"]])
    tg, x, fs = _uniform(t, np.asarray(gyro, float))
    omega, pk, chain, axis = _swing(tg, x, fs, params, None, impacts=impacts)
    for cand in _candidate_axes(x, fs, params)[1:]:  # 가장 긴 사슬을 주는 축을 첫 축으로
        trial = _swing(tg, x, fs, params, None, impacts=impacts, axis=cand)
        if trial[2] is not None and (chain is None or trial[2][1] - trial[2][0] > chain[1] - chain[0]):
            omega, pk, chain, axis = trial
    if chain is not None:  # 흔들기 구간에서 축을 다시 구한다(부호는 처음 축에 맞춘다)
        refined = _swing(tg, x, fs, params, (tg[pk[chain[0]]] - 0.5 / fs, tg[pk[chain[1]]] + 0.5 / fs),
                         ref_axis=axis, impacts=impacts)
        if refined[2] is not None:
            omega, pk, chain, _ = refined
    if chain is None:
        out["flags"].append("no_swing")
        return out
    # 같은 방향 봉우리로 세면 흔들기의 시작·끝 위상에 따라 주기 수가 하나 다를 수 있다: 양쪽 방향 중 긴 사슬을 쓴다
    p0 = float(np.median(np.diff(_peak_times(tg, omega, pk, fs)[chain[0]:chain[1] + 1])))
    wide = (tg[pk[chain[0]]] - p0, tg[pk[chain[1]]] + p0)
    best = None
    for sign in (1.0, -1.0):
        pk_s, ch_s = _chain(tg, sign * omega, fs, params, wide, impacts)
        if ch_s is not None and (best is None or ch_s[1] - ch_s[0] > best[2][1] - best[2][0]):
            best = (sign * omega, pk_s, ch_s)
    if best is not None:
        omega, pk, chain = best
    tp = _peak_times(tg, omega, pk, fs)[chain[0]:chain[1] + 1]
    iv = np.diff(tp)
    kept = iv[1:-1]
    out.update(swing_period_s=float(np.median(kept)), n_cycles=len(kept), n_cycles_total=len(iv),
               swing_t0_s=float(tp[0]), swing_t1_s=float(tp[-1]))
    if len(iv) < params["pendulum.min_cycles"]:
        out["flags"].append("few_cycles")
    # 흔들기 구간 밖에 다른 고른 리듬(예: 정강이 폰으로 걸은 구간)이 있으면 사람이 확인하게 표시한다
    pk_all, _ = _chain(tg, omega, fs, params, None, impacts)
    t_all = _peak_times(tg, omega, pk_all, fs)
    half = out["swing_period_s"] / 2
    other = _longest_chain(t_all[(t_all < tp[0] - half) | (t_all > tp[-1] + half)], params)
    if other is not None and other[1] - other[0] >= params["pendulum.min_cycles"] // 2:
        t_o = t_all[(t_all < tp[0] - half) | (t_all > tp[-1] + half)][other[0]:other[1] + 1]
        if abs(float(np.median(np.diff(t_o))) / out["swing_period_s"] - 1) > params["pendulum.regular_tol_frac"]:
            out["flags"].append("other_rhythm")
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
