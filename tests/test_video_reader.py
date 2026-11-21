"""영상 판독 도구(tools/video, D-83)의 디딤 줄 찾기를 합성 x–t 신호로 확인한다(영상 없이)."""

import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("PIL")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "video"))
import read_exp2_video as rv  # noqa: E402

STEP_S, STEP_PX, STANCE_S, X0, T0 = 0.5, 40.0, 0.6, 200.0, 2.0  # 0.5 s마다 40 px씩(80 px/s), 디딤 0.6 s
XA, XB = 420.0, 1620.0  # 디딤 자리와 겹치지 않게 둔 두 기준 x(물병)


def signal(skip: tuple[int, ...] = (), direction: int = 1) -> np.ndarray:
    """디딤마다 같은 x에 0.6 s 머무는 밝은 띠(폭 12 px, 세기 60). direction = −1이면 오른쪽에서 왼쪽."""
    s = np.zeros((int(30 * rv.FPS), rv.W), np.float32)
    for i in range(40):
        if i in skip:
            continue
        x = X0 + STEP_PX * i
        x = x if direction > 0 else rv.W - x
        k0, k1 = int(round((T0 + STEP_S * i) * rv.FPS)), int(round((T0 + STEP_S * i + STANCE_S) * rv.FPS))
        s[k0:k1, int(x) - 6:int(x) + 6] = 60.0
    return s


def test_chain_crossing_times_and_step_count():
    r = rv.analyse(signal(), "bright", XA, XB)
    assert r is not None and r["sgn"] == 1
    # 디딤 시작점을 이은 선: t = 2 + (x − 200) ÷ 80 → x = 420에서 4.75 s, x = 1620에서 19.75 s
    assert r["tA"] == pytest.approx(4.75, abs=0.05)
    assert r["tB"] == pytest.approx(19.75, abs=0.05)
    assert int(r["ins"].sum()) == 30  # 4.75 ≤ t < 19.75에 시작한 디딤(5.0, 5.5, …, 19.5 s)
    assert len(r["irr"]) == 0 and r["ST"][:, 4].sum() == 0
    assert r["miv"] == pytest.approx(STEP_S, abs=0.02) and r["mdx"] == pytest.approx(STEP_PX, abs=1.0)


def test_one_missing_step_is_filled_and_flagged():
    r = rv.analyse(signal(skip=(15,)), "bright", XA, XB)
    assert int(r["ins"].sum()) == 30
    filled = r["ST"][r["ST"][:, 4] > 0]
    assert len(filled) == 1 and filled[0, 0] == pytest.approx(T0 + STEP_S * 15, abs=0.03)


def test_three_missing_steps_are_filled():
    r = rv.analyse(signal(skip=(15, 16, 17)), "bright", XA, XB)
    assert int(r["ins"].sum()) == 30 and int(r["ST"][:, 4].sum()) == 3


def test_right_to_left_walk():
    r = rv.analyse(signal(direction=-1), "bright", rv.W - XB, rv.W - XA)
    assert r["sgn"] == -1
    assert abs(r["tA"] - r["tB"]) == pytest.approx(15.0, abs=0.05)


def test_cross_time_extrapolates_beyond_chain():
    st = np.array([[1.0, 1.5, 100.0, 50, 0], [1.5, 2.0, 140.0, 50, 0], [2.0, 2.5, 180.0, 50, 0]])
    t, ex = rv.cross_time(st, 120.0, 1)
    assert t == pytest.approx(1.25) and not ex
    t, ex = rv.cross_time(st, 220.0, 1)
    assert t == pytest.approx(2.5) and ex
