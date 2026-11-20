"""수직 점프 (SPEC §4.6, §5.7, DECISIONS D-37·D-77, QA Q17).

기록 하나(`E2_<사람>_J_1`)에 점프 3회. 점프마다:
1. 체공은 수직 비력 a_v(g)의 사건으로 찾는다(D-77): 이륙 = a_v가 `jump.push_min_g`(1.5 g) 이상인 밀기 뒤
   `jump.max_push_s` 안에 처음 `flight.a_thresh_g`(0.2 g) 아래로 내려간 시각(지면반력이 거의 0), 착지 충격 = 이륙 뒤
   처음 a_v ≥ `jump.impact_min_g`(2.0 g)인 곳(`jump.max_flight_s` 안), 착지 = 그 충격 앞에서 a_v가
   `jump.landing_level_g`(1.0 g)를 위로 지난 시각. t_f = 착지 − 이륙 ≥ `jump.min_flight_s`(아니면 점프가 아니다, 달리기
   걸음). 시각은 샘플 사이 선형 보간. h = g t_f² ÷ 8, v_flight = g t_f ÷ 2.
   공중에서 폰이 출렁여 크기가 0 g 근처에 머물지 않아도(2026-11-20 A 시험) 찾는다.
2. 가만히 선 구간: 앞 사건의 착지 뒤 ~ 이륙 사이에서 |a_v,total − 1| ≤ `jump.quiet_tol_g`가 `jump.quiet_s` 이상인
   마지막 구간. 그 평균을 1 g로 다시 맞춰(a_v ÷ 평균) 구간 끝부터 이륙까지 (a_v ÷ 평균 − 1) × g를 적분 = v_int.
   구간이 없거나 구간 끝이 이륙보다 `jump.max_prejump_s` 넘게 앞이면 점프로 세지 않는다(D-77. PROTOCOL §3.7은 2초
   가만히 선 뒤 뛴다. 기록 처음·끝에 폰을 만지는 흔들림이 점프처럼 보이는 것을 거른다). 번호는 센 점프에만 붙인다.
3. 밀기 구간 = 적분 속도가 마지막으로 0을 아래에서 위로 지난 시각(가장 낮은 자세) ~ 이륙. 평균 지면반력은
   시간 평균 1 + v_int ÷ (g t_push)(BW), 최대는 그 구간 a_v(BW)의 최댓값.
4. J = m v_flight, 운동에너지 ½ m v_flight². 체중이 없으면 NaN, flags=no_mass.
"""

from __future__ import annotations

import math

import numpy as np

from walkmusic.config import Params
from walkmusic.exp3 import _uniform
from walkmusic.metrics import jump_from_flight
from walkmusic.orientation import vertical_signal

NAN = float("nan")


def _crossing(t: np.ndarray, x: np.ndarray, i: int, level: float) -> float:
    """x[i-1]과 x[i] 사이에서 x가 level을 지나는 시각(선형 보간). i가 0이면 t[0]."""
    if i <= 0 or i >= len(x):
        return float(t[min(max(i, 0), len(t) - 1)])
    x0, x1 = x[i - 1], x[i]
    f = 0.0 if x1 == x0 else (level - x0) / (x1 - x0)
    return float(t[i - 1] + np.clip(f, 0.0, 1.0) * (t[i] - t[i - 1]))


def _last_quiet(ok: np.ndarray, lo: int, hi: int, need: int) -> tuple[int, int] | None:
    """ok[lo:hi]에서 길이 need 이상인 True 연속 구간 중 마지막의 [시작, 끝)."""
    best, i = None, lo
    while i < hi:
        if ok[i]:
            j = i
            while j < hi and ok[j]:
                j += 1
            if j - i >= need:
                best = (i, j)
            i = j
        else:
            i += 1
    return best


def _jump_events(tg: np.ndarray, av: np.ndarray, fs: float, params: Params) -> list[tuple[int, float, float]]:
    """점프마다 (이륙 인덱스 j, 이륙 시각, 착지 시각). av[j-1] > 0.2 g ≥ av[j], 착지는 1 g를 위로 지난 시각(D-77)."""
    push, impact = params["jump.push_min_g"], params["jump.impact_min_g"]
    to_level, land_level = params["flight.a_thresh_g"], params["jump.landing_level_g"]
    max_push = int(round(params["jump.max_push_s"] * fs))
    max_f = int(round(params["jump.max_flight_s"] * fs))
    out, i, n = [], 0, len(av)
    while i < n:
        if av[i] < push:
            i += 1
            continue
        j = i
        while j < n and av[j] > to_level and j - i <= max_push:
            j += 1
        if j >= n or av[j] > to_level:  # 밀기 뒤 0.2 g 아래로 안 내려갔다(걸음, 착지 뒤 흔들림)
            i += 1
            continue
        k = j
        while k < n and av[k] < impact and k - j <= max_f:
            k += 1
        if k >= n or av[k] < impact:  # 이륙 뒤 착지 충격이 없다
            i = j + 1
            continue
        m = k
        while m > j and av[m - 1] >= land_level:
            m -= 1
        t_to, t_land = _crossing(tg, av, j, to_level), _crossing(tg, av, m, land_level)
        if t_land - t_to < params["jump.min_flight_s"]:  # 이륙 뒤 첫 충격이 너무 이르다(달리기 걸음)
            i = j + 1
            continue
        out.append((j, t_to, t_land))
        i = k
        while i < n and av[i] >= push:  # 착지 충격이 끝날 때까지 건너뛴다
            i += 1
    return out


def q17_status(n_found: int, params: Params) -> str:
    """QA Q17: 점프 수가 `jump.n_jumps`면 PASS, 다르면 WARN, 0개면 FAIL."""
    if n_found == 0:
        return "FAIL"
    return "PASS" if n_found == params["jump.n_jumps"] else "WARN"


def analyze_jumps(t: np.ndarray, total_g: np.ndarray, gravity: np.ndarray, params: Params,
                  mass_kg: float) -> list[dict]:
    """점프 기록 → 점프마다 한 줄(jumps.csv의 열). total_g는 총 가속도(g, N×3), gravity는 방향용."""
    g = params["constants.g"]
    tg, x, fs = _uniform(np.asarray(t, float), np.column_stack([total_g, gravity]))
    av = vertical_signal(x[:, :3], x[:, 3:])
    ok = np.abs(av - 1.0) <= params["jump.quiet_tol_g"]
    need = int(math.ceil(params["jump.quiet_s"] * fs - 1e-9))
    rows, prev_end = [], 0
    for i, t_to, t_land in _jump_events(tg, av, fs, params):
        quiet = _last_quiet(ok, prev_end, i, need)
        prev_end = int(np.searchsorted(tg, t_land))
        if quiet is None or tg[i] - tg[quiet[1] - 1] > params["jump.max_prejump_s"]:
            continue  # 가만히 선 구간에서 시작하지 않았다: 폰을 만진 흔들림 등(D-77)
        tf = t_land - t_to
        kin = jump_from_flight(tf, mass_kg, g)
        flags = []
        if not np.isfinite(mass_kg):
            flags.append("no_mass")
        row = dict(jump_no=len(rows) + 1, takeoff_s=t_to, landing_s=t_land, flight_time_s=tf,
                   height_m=kin["height_m"], takeoff_v_flight_ms=kin["takeoff_v_ms"], takeoff_v_int_ms=NAN,
                   impulse_ns=kin["impulse_ns"], kinetic_energy_j=kin["kinetic_energy_j"], pushoff_time_s=NAN,
                   mean_grf_push_bw=NAN, peak_grf_push_bw=NAN, quiet_mean_g=NAN)
        q0, q1 = quiet
        base = float(av[q0:q1].mean())
        bw = av / base
        acc = (bw[q1 - 1:i + 1] - 1.0) * g
        v = np.concatenate([[0.0], np.cumsum((acc[1:] + acc[:-1]) / 2) / fs])  # tg[q1-1] … tg[i]
        frac = (t_to - tg[i - 1]) * fs  # 이륙 사건 시각까지
        v_to = float(v[-2] + frac * (v[-1] - v[-2]))
        ups = np.where((v[:-1] <= 0) & (v[1:] > 0))[0]
        t_low = _crossing(tg[q1 - 1:i + 1], v, ups[-1] + 1, 0.0) if len(ups) else NAN
        if np.isfinite(t_low) and t_low < t_to:
            push = (tg >= t_low) & (tg <= t_to)
            t_push = t_to - t_low  # 평균은 시간 평균 = 1 + v_int ÷ (g t_push) (SPEC §4.6, 샘플 평균은 끝을 덜 담는다)
            row.update(pushoff_time_s=t_push, mean_grf_push_bw=1.0 + v_to / (g * t_push),
                       peak_grf_push_bw=float(bw[push].max()))
        else:
            flags.append("no_countermovement")
        row.update(takeoff_v_int_ms=v_to, quiet_mean_g=base)
        row["flags"] = ";".join(flags)
        rows.append(row)
    return rows
