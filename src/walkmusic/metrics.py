"""지표 계산 순수 함수 (SPEC §4, §9). 파일을 읽거나 쓰지 않는다.

실험 2·3 식(Fr, 체공, 진자, 점프, 달리기 스프링, 분절 진자, 무릎 각, 역진자 보폭, Bland–Altman)은 여기 순수 함수로 두고
exp2·exp3·jumps가 쓴다(D-53). 숫자 예는 SPEC §9 #1–31, 손계산 노트 HANDCALC 1–11과 같다.
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


# --- 실험 2·3 손계산 식 (SPEC §4.4, §4.6, §5.10, §9 #21–30, HANDCALC 4–11) ---


def jump_from_flight(flight_time_s: float, mass_kg: float, g: float) -> dict[str, float]:
    """체공 시간으로 본 수직 점프 (SPEC §4.6). 이륙·착지 때 몸 중심 높이가 같다고 본다.

    height_m = g t_f² ÷ 8, takeoff_v_ms = g t_f ÷ 2, impulse_ns = m v (N·s), kinetic_energy_j = ½ m v² (J).
    """
    v = g * flight_time_s / 2.0
    return dict(height_m=rise_height_m(flight_time_s, g), takeoff_v_ms=v, impulse_ns=mass_kg * v,
                kinetic_energy_j=0.5 * mass_kg * v**2)


def pushoff_mean_grf_bw(takeoff_v_ms: float, pushoff_time_s: float, g: float) -> float:
    """밀기 구간 평균 지면반력 (체중 배수) = 1 + v ÷ (g t_push) (SPEC §4.6)."""
    return 1.0 + takeoff_v_ms / (g * pushoff_time_s)


def frames_to_seconds(frames: float, fps: float) -> float:
    """영상 프레임 수 → 시간 (s)."""
    return frames / fps


def height_per_frame_m(flight_time_s: float, fps: float, g: float) -> float:
    """체공 1프레임 차이가 만드는 높이 차이 (m), 1차 근사 dh = (g t_f ÷ 4) ÷ fps (SPEC §9 #23)."""
    return g * flight_time_s / 4.0 / fps


def running_flight(speed_ms: float, flight_time_s: float, g: float) -> dict[str, float]:
    """달리기 한 걸음의 체공을 포물선으로 본다 (SPEC §4.6). v_y = g t_f ÷ 2, θ = arctan(v_y ÷ v)."""
    vy = g * flight_time_s / 2.0
    return dict(vertical_v_ms=vy, takeoff_angle_deg=math.degrees(math.atan2(vy, speed_ms)),
                air_distance_m=speed_ms * flight_time_s, rise_height_m=rise_height_m(flight_time_s, g))


def spring_mass(mass_kg: float, contact_time_s: float, flight_time_s: float, speed_ms: float,
                leg_length_m: float, g: float) -> dict[str, float]:
    """달리기 스프링(Morin et al., 2005; SPEC §4.6). 접촉 중 지면반력을 반 사인파로 본다.

    F_max = m g (π ÷ 2)(t_f ÷ t_c + 1), Δy = F_max t_c² ÷ (m π²) − g t_c² ÷ 8,
    ΔL = L − √(L² − (v t_c ÷ 2)²) + Δy, k_vert = F_max ÷ Δy, k_leg = F_max ÷ ΔL (kN/m로 낸다),
    탄성에너지 = ½ k_vert Δy² (J), 접촉 중 평균 지면반력 = (t_c + t_f) ÷ t_c (BW).
    """
    tc, tf = contact_time_s, flight_time_s
    fmax = mass_kg * g * (math.pi / 2.0) * (tf / tc + 1.0)
    dy = fmax * tc**2 / (mass_kg * math.pi**2) - g * tc**2 / 8.0
    dl = leg_length_m - math.sqrt(leg_length_m**2 - (speed_ms * tc / 2.0) ** 2) + dy
    kvert = fmax / dy
    return dict(fmax_n=fmax, fmax_bw=fmax / (mass_kg * g), delta_y_m=dy, delta_l_m=dl, kvert_kn_m=kvert / 1000.0,
                kleg_kn_m=fmax / dl / 1000.0, elastic_energy_j=0.5 * kvert * dy**2,
                mean_grf_contact_bw=(tc + tf) / tc)


def segment_pendulum(mass_kg: float, thigh_m: float, shank_m: float, knee_flexion_deg: float, g: float,
                     fractions: dict[str, float]) -> dict[str, float]:
    """허벅지 + 정강이·발 두 분절 물리 진자 (SPEC §4.4, D-41).

    fractions: thigh_mass, thigh_com, thigh_kcm, shank_mass, shank_com, shank_kcm (`pendulum.seg_*_frac`).
    엉덩관절 원점, 허벅지가 x축. 정강이·발 질량중심 = (l_t + c_s l_s cos φ, c_s l_s sin φ).
    돌려주는 값: mass_kg(두 분절 합), inertia_hip_kgm2(평행축 정리), com_dist_m(엉덩관절 → 전체 질량중심),
    period_s = 2π √(I ÷ (m g d)).
    """
    phi = math.radians(knee_flexion_deg)
    m_t, m_s = fractions["thigh_mass"] * mass_kg, fractions["shank_mass"] * mass_kg
    r_t = fractions["thigh_com"] * thigh_m
    c_s = fractions["shank_com"] * shank_m
    x_s, y_s = thigh_m + c_s * math.cos(phi), c_s * math.sin(phi)
    inertia = (m_t * ((fractions["thigh_kcm"] * thigh_m) ** 2 + r_t**2)
               + m_s * ((fractions["shank_kcm"] * shank_m) ** 2 + x_s**2 + y_s**2))
    m_sum = m_t + m_s
    d = math.hypot((m_t * r_t + m_s * x_s) / m_sum, m_s * y_s / m_sum)
    return dict(mass_kg=m_sum, inertia_hip_kgm2=inertia, com_dist_m=d,
                period_s=2.0 * math.pi * math.sqrt(inertia / (m_sum * g * d)))


def pendulum_energy(mass_kg: float, com_dist_m: float, inertia_kgm2: float, amplitude_deg: float,
                    g: float) -> dict[str, float]:
    """진자 에너지와 토크 (SPEC §4.4, HANDCALC 8·9). 꼭대기 위치에너지 m g d (1 − cos θ) = 바닥 ½ I ω².

    돌려주는 값: potential_energy_j, omega_pred_rad_s = √(2 m g d (1 − cos θ) ÷ I),
    gravity_torque_nm = m g d sin θ, angular_accel_rad_s2 = τ ÷ I.
    """
    th = math.radians(amplitude_deg)
    pe = mass_kg * g * com_dist_m * (1.0 - math.cos(th))
    tau = mass_kg * g * com_dist_m * math.sin(th)
    return dict(potential_energy_j=pe, omega_pred_rad_s=math.sqrt(2.0 * pe / inertia_kgm2),
                gravity_torque_nm=tau, angular_accel_rad_s2=tau / inertia_kgm2)


def knee_angles(hip_xy: Sequence[float], knee_xy: Sequence[float], ankle_xy: Sequence[float]) -> dict[str, float]:
    """영상 마커(대전자·무릎·바깥 복사뼈 픽셀 좌표)의 무릎 각 (SPEC §5.7, 코사인 법칙).

    knee_inner_deg = 무릎 안쪽 각, knee_flexion_deg = 180 − 안쪽 각,
    leg_angle_deg = arctan(Δx ÷ Δy) (대전자 → 복사뼈 선과 수직선 사이).
    """
    hip, knee, ankle = (np.asarray(p, dtype=float) for p in (hip_xy, knee_xy, ankle_xy))
    a, b, c = np.linalg.norm(knee - hip), np.linalg.norm(ankle - knee), np.linalg.norm(ankle - hip)
    inner = math.degrees(math.acos(float(np.clip((a**2 + b**2 - c**2) / (2 * a * b), -1.0, 1.0))))
    dx, dy = ankle - hip
    return dict(knee_inner_deg=inner, knee_flexion_deg=180.0 - inner, leg_angle_deg=math.degrees(math.atan2(dx, dy)))


def com_vertical_displacement_m(t_s: Sequence[float], total_vertical_accel_g: Sequence[float], g: float) -> float:
    """한 걸음(발 디딤 i ~ i+1) 안 몸 중심 수직 변위 h_com (m) (SPEC §4.3, D-40).

    (a_v,total − 1) × g에서 걸음 안 평균을 빼고 적분해 속도, 속도에서 다시 평균을 빼고 적분해 위치, 최고 − 최저.
    표본이 3개 미만이면 NaN.
    """
    t = np.asarray(t_s, dtype=float)
    a = (np.asarray(total_vertical_accel_g, dtype=float) - 1.0) * g
    if len(t) < 3:
        return float("nan")
    dt = np.diff(t)

    def integral(x: np.ndarray) -> np.ndarray:  # 사다리꼴 누적 적분(첫 값 0)
        return np.concatenate([[0.0], np.cumsum((x[1:] + x[:-1]) / 2.0 * dt)])

    span = t[-1] - t[0]
    a = a - integral(a)[-1] / span  # 평균은 시간 평균(적분 ÷ 걸음 길이)
    v = integral(a)
    v = v - integral(v)[-1] / span
    z = integral(v)
    return float(z.max() - z.min())


def step_length_zh(leg_length_m: float, com_vertical_m: float, correction: float) -> float:
    """역진자 보폭 SL_ZH = K · 2√(2 l h − h²) (m) (Zijlstra & Hof 2003, D-40). K = `com.zh_correction`."""
    h = com_vertical_m
    return correction * 2.0 * math.sqrt(2.0 * leg_length_m * h - h**2)


def bland_altman(method_a: Sequence[float], method_b: Sequence[float], ddof: int) -> dict[str, float]:
    """짝지은 두 방법의 Bland–Altman (SPEC §5.10). 차이 = A − B. 일치 한계 = bias ± 1.96 SD(ddof)."""
    a, b = np.asarray(method_a, dtype=float), np.asarray(method_b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = len(a)
    if n == 0:
        nan = float("nan")
        return dict(n=0, mean_a=nan, mean_b=nan, bias=nan, sd=nan, loa_low=nan, loa_high=nan, mean_abs_diff=nan)
    d = a - b
    bias = float(d.mean())
    sd = float(d.std(ddof=ddof)) if n > ddof else float("nan")
    return dict(n=n, mean_a=float(a.mean()), mean_b=float(b.mean()), bias=bias, sd=sd, loa_low=bias - 1.96 * sd,
                loa_high=bias + 1.96 * sd, mean_abs_diff=float(np.abs(d).mean()))
