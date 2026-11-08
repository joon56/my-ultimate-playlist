"""지표 계산 순수 함수 (SPEC §4, §9). 파일을 읽거나 쓰지 않는다.

실험 2·3 식(Fr, 체공, 진자, 음원 반올림)은 DECISIONS D-41에 따라 Phase 1에서는 함수만 둔다.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def cadence_from_count(n_steps: float, duration_s: float) -> float:
    """걸음 수 ÷ 시간 × 60 (걸음/분). 계획서 2.3의 정의."""
    return n_steps / duration_s * 60.0


def speed_mps(distance_m: float, duration_s: float) -> float:
    """속도 = 거리 ÷ 시간 (m/s)."""
    return distance_m / duration_s


def step_length_m(speed: float, cadence_spm: float) -> float:
    """보폭 SL = v ÷ (C ÷ 60) (m). speed는 m/s, cadence는 걸음/분."""
    return speed / (cadence_spm / 60.0)


def tempo_ratio_pct(bpm: float, pc_spm: float) -> float:
    """템포 비율 T = BPM ÷ PC × 100 (%)."""
    return bpm / pc_spm * 100.0


def tolerance_band(center: float, tol_pct: float) -> tuple[float, float]:
    """center ± tol_pct% 구간 (같은 단위)."""
    d = center * tol_pct / 100.0
    return center - d, center + d


def cadence_change_pct(c_spm: float, pc_spm: float) -> float:
    """케이던스 변화율 ΔC% = (C − PC) ÷ PC × 100."""
    return (c_spm - pc_spm) / pc_spm * 100.0


def follow_ratio(dc_pct: float, t_pct: float, exclude_low: float, exclude_high: float) -> float:
    """추종 비율 R = ΔC% ÷ (T − 100). exclude_low ≤ T ≤ exclude_high이면 NaN (sync.r_exclude_*)."""
    if exclude_low <= t_pct <= exclude_high:
        return float("nan")
    return dc_pct / (t_pct - 100.0)


def vertical_force_n(mass_kg: float, total_vertical_accel_ms2: float) -> float:
    """수직 지면반력 추정 F = m × a_v,total (N). a_v,total은 중력을 포함한 수직 가속도(m/s²)."""
    return mass_kg * total_vertical_accel_ms2


def force_over_bodyweight(total_vertical_accel_ms2: float, g: float) -> float:
    """F/BW = a_v,total ÷ g (체중 배수)."""
    return total_vertical_accel_ms2 / g


def froude(speed: float, leg_length_m: float, g: float) -> float:
    """Froude 수 Fr = v² ÷ (g · L)."""
    return speed**2 / (g * leg_length_m)


def speed_at_froude(fr: float, leg_length_m: float, g: float) -> float:
    """Fr가 주어졌을 때의 속도 v = √(Fr · g · L) (m/s)."""
    return math.sqrt(fr * g * leg_length_m)


def rise_height_m(flight_time_s: float, g: float) -> float:
    """체공 시간 t_f에서 몸 중심 상승 높이 h = g · t_f² ÷ 8 (m)."""
    return g * flight_time_s**2 / 8.0


def pendulum_period_model_s(leg_length_m: float, k_over_l: float, d_over_l: float, g: float) -> float:
    """곧게 편 다리 물리 진자 주기 P_model = 2π √(k² ÷ (g · d)) (s). k, d는 다리 길이 L의 비율."""
    k = k_over_l * leg_length_m
    d = d_over_l * leg_length_m
    return 2.0 * math.pi * math.sqrt(k**2 / (g * d))


def pendulum_cadence_spm(swing_period_s: float) -> float:
    """진자 예측 케이던스 C_pend = 120 ÷ P (걸음/분)."""
    return 120.0 / swing_period_s


def log_speed_decomposition(v0: float, v1: float, c0_spm: float, c1_spm: float) -> dict[str, float]:
    """Δln v = Δln SL + Δln C 분해 (SPEC §4.3, D-12). 기여율은 각 항 ÷ Δln v."""
    sl0, sl1 = step_length_m(v0, c0_spm), step_length_m(v1, c1_spm)
    dv, dc, dsl = math.log(v1 / v0), math.log(c1_spm / c0_spm), math.log(sl1 / sl0)
    return dict(step_length_0_m=sl0, step_length_1_m=sl1, dln_v=dv, dln_c=dc, dln_sl=dsl,
                contrib_cadence=dc / dv, contrib_step_length=dsl / dv)


def sync_counts(cadence_inst_spm: Sequence[float], bpm: float, tol_pct: float) -> dict[str, float]:
    """동조율 (SPEC §4.2). 분모는 넘겨준 유효 순간 케이던스의 개수.

    돌려주는 값: sync_pct(±tol_pct 안 비율, %), n_sync, n_half(BPM/2 ± tol), n_double(2·BPM ± tol), n.
    """
    c = np.asarray(cadence_inst_spm, dtype=float)

    def within(target: float) -> np.ndarray:
        return np.abs(c - target) <= tol_pct / 100.0 * target

    n = len(c)
    n_sync = int(within(bpm).sum())
    return dict(sync_pct=n_sync / n * 100.0 if n else float("nan"), n_sync=n_sync,
                n_half=int(within(bpm / 2).sum()), n_double=int(within(2 * bpm).sum()), n=n)


def cv_pct(values: Sequence[float], ddof: int) -> float:
    """변동계수 100 × SD ÷ 평균 (%). ddof는 stats.sd_ddof."""
    x = np.asarray(values, dtype=float)
    return float(x.std(ddof=ddof) / x.mean() * 100.0)


def tempo_file_bpm(pc_spm: float, ratio: float, step_bpm: float) -> float:
    """챌린지 음원 BPM = PC × 비율을 step_bpm 단위로 반올림(0.5는 올림, PROTOCOL 3.4)."""
    q = round(pc_spm * ratio / step_bpm, 9)  # 1.35·PC 같은 부동소수점 오차를 지운다
    return math.floor(q + 0.5) * step_bpm


def tempo_file_count(lo_bpm: float, hi_bpm: float, step_bpm: float) -> int:
    """lo–hi BPM을 step 간격으로 만든 음원 파일 수(양 끝 포함)."""
    return int(round((hi_bpm - lo_bpm) / step_bpm)) + 1


def min_flight_samples(fs_hz: float, min_duration_s: float) -> int:
    """체공으로 볼 최소 연속 샘플 수 ceil(min_duration × fs − 1e-9) (SPEC §5.7)."""
    return math.ceil(min_duration_s * fs_hz - 1e-9)


def flight_events(accel_mag_g: Sequence[float], fs_hz: float, a_thresh_g: float,
                  min_duration_s: float) -> list[tuple[int, int]]:
    """총 가속도 크기 < a_thresh_g가 min_flight_samples 이상 이어진 구간 [시작, 끝) 샘플 번호 목록."""
    below = np.asarray(accel_mag_g, dtype=float) < a_thresh_g
    need = min_flight_samples(fs_hz, min_duration_s)
    events, i, n = [], 0, len(below)
    while i < n:
        if below[i]:
            j = i
            while j < n and below[j]:
                j += 1
            if j - i >= need:
                events.append((i, j))
            i = j
        else:
            i += 1
    return events
