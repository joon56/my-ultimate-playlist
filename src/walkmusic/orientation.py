"""폰 방향: 수직 단위벡터와 방향 차이 (SPEC §5.3, DECISIONS D-30·D-35).

수직 방향 û는 Gravity.csv의 방향을 샘플마다 쓴다. 부호는 총 가속도의 수직 성분이 평균 +1 g가 되게 정한다.
"""

from __future__ import annotations

import numpy as np


def unit_rows(v: np.ndarray) -> np.ndarray:
    """행마다 단위벡터로 나눈다 (N×3)."""
    return v / np.linalg.norm(v, axis=1)[:, None]


def vertical_signal(total_g: np.ndarray, gravity: np.ndarray) -> np.ndarray:
    """총 가속도(g, N×3)의 수직 성분(g). 서 있을 때 +1 g, 발 디딤 충격은 위쪽 봉우리."""
    u = unit_rows(gravity)
    v = np.einsum("ij,ij->i", total_g, u)
    return v if np.mean(v) >= 0 else -v


def median_direction(gravity: np.ndarray) -> np.ndarray:
    """Gravity 방향들의 중앙 방향(단위벡터). Q14의 회차별 û."""
    m = np.median(unit_rows(gravity), axis=0)
    return m / np.linalg.norm(m)


def angle_deg(u: np.ndarray, v: np.ndarray) -> float:
    """두 방향 사이 각도(도)."""
    c = float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v)))
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))
