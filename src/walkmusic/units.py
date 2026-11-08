"""가속도 단위·중력 포함 여부·합성 부호 판별 (SPEC §5.2, DECISIONS D-29·D-30).

가정하지 않고 데이터로 정한다. 서 있는 구간 대신 기록 전체 통계를 쓴다(D-30):
- 단위: ‖Gravity‖ 중앙값이 약 1이면 g, 약 9.8이면 m/s².
- 중력 포함: Accelerometer 평균의 Gravity 방향 성분이 0 근처면 제외, ‖Gravity‖ 근처면 포함.
- 합성 부호(중력 제외일 때): AccelerometerUncalibrated가 있으면 A ± G와 잔차를 비교하고,
  없으면 수직 성분의 위쪽 봉우리(왜도)로 정한다.
판별에 실패하면 UnitsError(Q09 FAIL).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from walkmusic.io_sensorlogger import Recording
from walkmusic.orientation import unit_rows


class UnitsError(ValueError):
    """단위·부호를 판별하지 못했다."""


@dataclass
class Units:
    """판별 결과. g_scale은 같은 단위의 1 g 크기(‖Gravity‖ 중앙값)."""

    accel_units: str
    includes_gravity: bool
    combine_sign: int
    g_scale: float
    confidence: str
    evidence: dict = field(default_factory=dict)


def _unit_name(mag: float) -> str | None:
    if abs(mag - 1.0) < 0.2:
        return "g"
    if abs(mag - 9.81) < 1.0:
        return "m/s2"
    return None


def _upper_skew(v: np.ndarray) -> float:
    med = np.median(v)
    return float((np.percentile(v, 99) - med) - (med - np.percentile(v, 1)))


def _on(rec: Recording, name: str, t: np.ndarray) -> np.ndarray:
    tt, v = rec.t(name), rec.xyz(name)
    return np.column_stack([np.interp(t, tt, v[:, j]) for j in range(3)])


def determine_units(rec: Recording) -> Units:
    """Recording의 Accelerometer 단위와 중력 처리를 판별한다."""
    if not rec.has("Accelerometer"):
        raise UnitsError("Accelerometer가 없다")
    t = rec.t("Accelerometer")
    a = rec.xyz("Accelerometer")
    if not rec.has("Gravity"):  # SPEC §5.2 대안: 크기 중앙값만으로(중력 포함일 때만 가능)
        mag = float(np.median(np.linalg.norm(a, axis=1)))
        name = _unit_name(mag)
        if name is None:
            raise UnitsError(f"Gravity가 없고 ‖a‖ 중앙값 {mag:.3f}로는 판별할 수 없다")
        return Units(name, True, 0, mag, "low", {"accel_mag_median": mag})
    g = _on(rec, "Gravity", t)
    g_mag = float(np.median(np.linalg.norm(g, axis=1)))
    g_units = _unit_name(g_mag)
    if g_units is None:
        raise UnitsError(f"‖Gravity‖ 중앙값 {g_mag:.3f}가 1도 9.8도 아니다")
    par = float(np.mean(np.einsum("ij,ij->i", a, unit_rows(g))))
    ev = {"gravity_mag_median": g_mag, "accel_mean_along_gravity": par}
    if abs(abs(par) - g_mag) < 0.2 * g_mag:
        return Units(g_units, True, 0, g_mag, "high", ev)
    if abs(par) > 0.2 * g_mag:
        raise UnitsError(f"Accelerometer 평균의 Gravity 방향 성분 {par:.3f}이 0도 ‖G‖도 아니다")
    cand = {s: a + s * g for s in (1, -1)}
    skew = {s: _upper_skew(np.einsum("ij,ij->i", cand[s], unit_rows(g)) * np.sign(
        np.mean(np.einsum("ij,ij->i", cand[s], unit_rows(g))))) for s in (1, -1)}
    ev.update({f"upper_skew_{'+' if s > 0 else '-'}": v for s, v in skew.items()})
    s_skew = 1 if skew[1] > skew[-1] else -1
    if rec.has("AccelerometerUncalibrated"):
        u = _on(rec, "AccelerometerUncalibrated", t)
        k = g_mag / float(np.median(np.linalg.norm(u, axis=1)))
        res = {s: float(np.median(np.linalg.norm(cand[s] - k * u, axis=1))) for s in (1, -1)}
        ev.update({"uncal_scale": k, "resid_plus": res[1], "resid_minus": res[-1]})
        s_res = 1 if res[1] < res[-1] else -1
        if min(res.values()) < 0.2 * max(res.values()):
            conf = "high" if s_res == s_skew else "low"
            return Units(g_units, False, s_res, g_mag, conf, ev)
    return Units(g_units, False, s_skew, g_mag, "low", ev)


def total_accel_g(rec: Recording, units: Units) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(t_s, 총 가속도 g (N×3), Gravity (N×3, 원래 단위)). Accelerometer 시각 기준."""
    t = rec.t("Accelerometer")
    a = rec.xyz("Accelerometer")
    g = _on(rec, "Gravity", t) if rec.has("Gravity") else np.tile(np.median(a, axis=0), (len(t), 1))
    total = a if units.includes_gravity else a + units.combine_sign * g
    return t, total / units.g_scale, g
