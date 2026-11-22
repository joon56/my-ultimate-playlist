"""마커 추적 결과(<stem>_markers.npz)에서 진자 10번 흔들림 시간을 읽는다.

사용: python -I tools/video/swing_read.py <출력 폴더> <stem> [<stem> ...] [--plot]

방법
1. 노랑(발목) 테이프 중심이 가장 크게 움직이는 방향(주성분)으로 잰 위치 s(t). 0.12 s 창으로 고른다(2차 다항식).
2. 같은 쪽 끝점(극대, 극소 따로): 두드러짐이 12 px 이상이고 큰 흔들림(두드러짐 90 백분위)의 10% 이상이며 0.6 s 이상 떨어진
   봉우리(서 있는 동안의 작은 흔들림은 세지 않는다). 간격이 중앙값의 ±25% 안으로 이어진 가장 긴
   줄이 '이어진 흔들림'. 끝점 시각은 봉우리 둘레 세 점의 포물선 꼭짓점(프레임 시각은 pts).
3. swing_10 = 이어진 흔들림의 두 번째 끝점에서 열두 번째 끝점까지의 시간(첫 주기는 뺀다). 끝점이 11개뿐이면 첫 번째에서
   열한 번째까지. 11개가 안 되면 내지 않는다. 극대로 잰 값과 극소로 잰 값의 평균을 쓴다(한쪽만 되면 그쪽).
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks, savgol_filter

PROM_PX, REL_PROM, MIN_SEP_S, TOL = 12.0, 0.10, 0.6, 0.25


def series(z) -> tuple[np.ndarray, np.ndarray]:
    t, Y = z["t"], z["yellow"]
    ok = np.flatnonzero(np.isfinite(Y[:, 0]))
    cut = np.flatnonzero(np.diff(t[ok]) > 0.25)  # 추적이 0.25 s 넘게 끊긴 곳에서 나누고 가장 긴 토막만 쓴다
    parts = np.split(ok, cut + 1)
    ok = max(parts, key=len)
    t, Y = t[ok], Y[ok]
    c = Y - np.median(Y, axis=0)
    w, v = np.linalg.eigh(np.cov(c.T))
    s = c @ v[:, -1]
    fps = 1.0 / float(np.median(np.diff(t)))
    win = max(int(round(0.12 * fps)) // 2 * 2 + 1, 5)
    return t, savgol_filter(s, win, 2)


def extremes(t: np.ndarray, s: np.ndarray, sign: int) -> np.ndarray:
    fps = 1.0 / float(np.median(np.diff(t)))
    pk, pr = find_peaks(sign * s, prominence=PROM_PX, distance=int(MIN_SEP_S * fps))
    if len(pk):  # 서 있는 동안의 작은 흔들림은 세지 않는다: 큰 흔들림(두드러짐 90 백분위)의 10%에 못 미치는 봉우리를 뺀다
        pk = pk[pr["prominences"] >= max(PROM_PX, REL_PROM * float(np.percentile(pr["prominences"], 90)))]
    out = []
    for p in pk:
        if 0 < p < len(s) - 1:
            y0, y1, y2 = sign * s[p - 1], sign * s[p], sign * s[p + 1]
            den = y0 - 2 * y1 + y2
            off = 0.5 * (y0 - y2) / den if den != 0 else 0.0
            out.append(t[p] + off * (t[p + 1] - t[p - 1]) / 2)
    return np.array(out)


def chain(tp: np.ndarray) -> np.ndarray:
    if len(tp) < 3:
        return tp
    iv = np.diff(tp)
    best = (0, 0)
    for i in range(len(iv)):
        j = i
        while j < len(iv):
            med = float(np.median(iv[i:j + 1]))
            if np.all(np.abs(iv[i:j + 1] - med) <= TOL * med):
                j += 1
            else:
                break
        if j - i > best[1] - best[0]:
            best = (i, j)
    return tp[best[0]:best[1] + 1]


def swing10(tp: np.ndarray):
    if len(tp) >= 12:
        return float(tp[11] - tp[1]), (1, 11)
    if len(tp) >= 11:
        return float(tp[10] - tp[0]), (0, 10)
    return None, None


def analyse(out: Path, stem: str) -> dict:
    z = np.load(out / f"{stem}_markers.npz")
    t, s = series(z)
    r = dict(stem=stem)
    vals = []
    for name, sign in (("max", 1), ("min", -1)):
        tp = chain(extremes(t, s, sign))
        v, idx = swing10(tp)
        iv = np.diff(tp)
        r[name] = dict(n_extremes=int(len(tp)), t_first=float(tp[0]) if len(tp) else None, t_last=float(tp[-1]) if len(tp) else None,
                       swing10_s=v, used=idx, period_median_s=float(np.median(iv)) if len(iv) else None,
                       period_mean_s=float(np.mean(iv)) if len(iv) else None, times=[round(float(x), 4) for x in tp])
        if v is not None:
            vals.append(v)
    r["swing10_s"] = float(np.mean(vals)) if vals else None
    r["amp_px"] = float((np.percentile(s, 97) - np.percentile(s, 3)) / 2)
    return r, t, s


if __name__ == "__main__":
    out = Path(sys.argv[1])
    stems = [a for a in sys.argv[2:] if not a.startswith("--")]
    plot = "--plot" in sys.argv
    res = []
    for stem in stems:
        r, t, s = analyse(out, stem)
        res.append(r)
        mx, mn = r["max"], r["min"]
        f = lambda v, n=3: "없음" if v is None else f"{v:.{n}f}"
        print(f"{stem:<14} 끝점 {mx['n_extremes']:2d}/{mn['n_extremes']:2d}개 | swing_10 극대 {f(mx['swing10_s'])} 극소 {f(mn['swing10_s'])} 평균 {f(r['swing10_s'])} s"
              f" | 주기 중앙 {f(mx['period_median_s'])}/{f(mn['period_median_s'])} s | 이어진 구간 {f(mx['t_first'], 2)}–{f(mx['t_last'], 2)} s")
        if plot:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(13, 3))
            ax.plot(t, s, lw=0.8)
            for name, col in (("max", "r"), ("min", "g")):
                for x in r[name]["times"]:
                    ax.axvline(x, color=col, lw=0.6)
            ax.set_title(f"{stem}: yellow tape along principal axis (px)")
            fig.tight_layout()
            fig.savefig(out / f"{stem}_swing.png", dpi=70)
            plt.close(fig)
    (out / "swing_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
