"""수직 점프 영상(옆에서, 슬로모션)에서 체공 시간을 읽는다. 화소만 읽는다.

사용(저장소 맨 위에서): python -I tools/video/jump_read.py <영상> <출력 폴더> --crop x y w h [--frac 0.5] [--plot]

방법
1. 프레임마다 발 둘레 화면에서 신발 아래 끝 y_b를 찾는다: 밝기 = 가장 어두운 색 채널, 문턱 = 그 프레임의 바닥 밝기(중앙값) +
   frac × (신발 밝기(98 백분위) − 바닥 밝기). 조명이 프레임마다 깜빡여서 문턱을 프레임마다 다시 잡는다. 문턱을 넘는 화소가
   4개 이상 있는 가장 아래 줄이 y_b.
2. 점프 = y_b가 앞뒤 1.5 s의 가장 낮은 자리보다 120 px 넘게 올라간 봉우리. 닿은 높이는 봉우리 0.9–0.5 s 앞(뒤)의 중앙값.
3. 이륙·착지 시각 = y_b(t)에 이어진 두 직선(꺾이는 점 하나, 두 기울기 자유, 홀·짝 프레임 어긋남 한 항)을 맞춘 꺾이는 점.
   창: 이륙은 '닿은 높이에서 6 px 안에 있던 마지막 프레임'의 앞 14·뒤 8프레임, 착지는 '닿은 높이의 6 px 안으로 돌아온 첫
   프레임'의 앞 8·뒤 14프레임. 시각은 컨테이너 pts.
4. 체공 시간 = 착지 − 이륙. 0.20 s보다 짧으면 점프로 치지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vframes as fr  # noqa: E402

WIDE, NARROW, NEAR_PX, PROM_PX, MIN_FLIGHT_S = 14, 8, 6, 120, 0.20


def track(video: Path, out: Path, crop, frac: float) -> tuple[np.ndarray, np.ndarray]:
    cache = out / f"{video.stem}_yb.npz"
    pts = fr.pts_table(video, out)
    if cache.exists():
        z = np.load(cache)
        if list(z["crop"]) == list(crop) and float(z["frac"]) == frac:
            return pts, z["yb"]
    yb = np.full(len(pts), np.nan)
    for n, _, a in fr.frames(video, 0.0, float(pts[-1]), crop, 1.0, pts):
        lum = a.astype(np.float32).min(axis=2)
        floor, shoe = float(np.median(lum)), float(np.percentile(lum, 98))
        ys = np.flatnonzero((lum > floor + frac * (shoe - floor)).sum(axis=1) >= 4)
        if len(ys):
            yb[n] = ys.max() + crop[1]
    np.savez(cache, yb=yb, crop=np.array(crop), frac=frac)
    return pts, yb


def hinge(t: np.ndarray, y: np.ndarray, par: np.ndarray) -> dict:
    """이어진 두 직선의 꺾이는 점을 격자로 찾는다. y = a + s1·(t − tb) [t < tb], a + s2·(t − tb) [t ≥ tb], + c·홀짝."""
    best = None
    for tb in np.arange(t[2], t[-3], (t[-1] - t[0]) / (len(t) - 1) / 20):
        d = t - tb
        X = np.column_stack([np.ones_like(t), np.where(d < 0, d, 0.0), np.where(d >= 0, d, 0.0), par])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ coef
        sse = float(r @ r)
        if best is None or sse < best["sse"]:
            best = dict(tb=float(tb), level=float(coef[0]), s1=float(coef[1]), s2=float(coef[2]), parity=float(coef[3]), sse=sse,
                        rms=float(np.sqrt(sse / len(t))))
    return best


def find_jumps(pts: np.ndarray, yb: np.ndarray) -> list[dict]:
    from scipy.signal import find_peaks
    fps = 1.0 / float(np.median(np.diff(pts)))
    pk, _ = find_peaks(-yb, prominence=PROM_PX, distance=int(0.6 * fps))
    out = []
    for p in pk:
        a0, a1 = np.searchsorted(pts, pts[p] - 0.9), np.searchsorted(pts, pts[p] - 0.5)
        b0, b1 = np.searchsorted(pts, pts[p] + 0.5), np.searchsorted(pts, pts[p] + 0.9)
        if a1 - a0 < 10 or b1 - b0 < 10:
            continue
        pre, post = float(np.median(yb[a0:a1])), float(np.median(yb[b0:b1]))
        n0 = p
        while n0 > a0 and yb[n0] < pre - NEAR_PX:
            n0 -= 1          # 닿은 높이에서 6 px 안에 있던 마지막 프레임
        n1 = p
        while n1 < b1 and yb[n1] < post - NEAR_PX:
            n1 += 1          # 닿은 높이의 6 px 안으로 돌아온 첫 프레임
        out.append(dict(apex=int(p), pre=pre, post=post, n0=int(n0), n1=int(n1)))
    return out


def flights(pts: np.ndarray, yb: np.ndarray) -> tuple[list[dict], list]:
    """신발 아래 끝 높이 y_b(t)에서 점프마다 이륙·착지 시각과 체공 시간을 낸다."""
    par = (np.arange(len(pts)) % 2).astype(float)
    res, fits, k = [], [], 0
    fidx = lambda t: float(np.interp(t, pts, np.arange(len(pts))))
    for j in find_jumps(pts, yb):
        i0, i1 = j["n0"] - WIDE, j["n0"] + NARROW
        j0, j1 = j["n1"] - NARROW, j["n1"] + WIDE
        if i0 < 0 or j1 >= len(pts):
            continue
        to = hinge(pts[i0:i1 + 1], yb[i0:i1 + 1], par[i0:i1 + 1])
        ld = hinge(pts[j0:j1 + 1], yb[j0:j1 + 1], par[j0:j1 + 1])
        tf = ld["tb"] - to["tb"]
        if tf < MIN_FLIGHT_S:  # 점프가 아니다(끝에서 걸어 나가는 장면 등)
            continue
        k += 1
        res.append(dict(jump_no=k, apex_frame=j["apex"], takeoff_s=to["tb"], landing_s=ld["tb"], flight_s=tf,
                        takeoff_frame=fidx(to["tb"]), landing_frame=fidx(ld["tb"]), level_pre_px=j["pre"], level_post_px=j["post"],
                        apex_px=float(yb[j["apex"]]), slopes_px_s=(to["s1"], to["s2"], ld["s1"], ld["s2"]),
                        parity_px=(to["parity"], ld["parity"]), rms_px=(to["rms"], ld["rms"])))
        fits.append(((i0, i1), to, (j0, j1), ld))
    return res, fits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--crop", type=int, nargs=4, required=True)
    ap.add_argument("--frac", type=float, default=0.5)
    ap.add_argument("--plot", action="store_true")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    pts, yb = track(a.video, a.out, a.crop, a.frac)
    print(f"프레임 {len(pts)}, 신발을 못 찾은 프레임 {int((~np.isfinite(yb)).sum())}")
    res, fits = flights(pts, yb)
    for r, ((i0, i1), to, (j0, j1), ld) in zip(res, fits):
        print(f"점프 {r['jump_no']}: 이륙 {r['takeoff_s']:.4f} s(프레임 {r['takeoff_frame']:.1f}), 착지 {r['landing_s']:.4f} s(프레임 {r['landing_frame']:.1f}), "
              f"체공 {r['flight_s']:.4f} s | 기울기 px/s 이륙 앞 {to['s1']:.0f} 뒤 {to['s2']:.0f}, 착지 앞 {ld['s1']:.0f} 뒤 {ld['s2']:.0f} | "
              f"홀짝 {to['parity']:.1f}/{ld['parity']:.1f} px, 잔차 {to['rms']:.2f}/{ld['rms']:.2f} px | 닿은 높이 {r['level_pre_px']:.0f}/{r['level_post_px']:.0f}, "
              f"꼭대기 {r['apex_px']:.0f}")
    (a.out / f"{a.video.stem}_jumps.json").write_text(json.dumps(dict(video=a.video.name, crop=a.crop, frac=a.frac, jumps=res), ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    if a.plot and res:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(len(res), 2, figsize=(11, 3.2 * len(res)), squeeze=False)
        for k, ((i0, i1), to, (j0, j1), ld) in enumerate(fits):
            for c, (b0, b1, h, name) in enumerate(((i0, i1, to, "takeoff"), (j0, j1, ld, "landing"))):
                n = np.arange(b0, b1 + 1)
                t = pts[b0:b1 + 1]
                ax[k, c].plot(n[n % 2 == 0], yb[n[n % 2 == 0]], "o", ms=4, label="even frames")
                ax[k, c].plot(n[n % 2 == 1], yb[n[n % 2 == 1]], "s", ms=4, label="odd frames")
                d = t - h["tb"]
                ax[k, c].plot(n, h["level"] + np.where(d < 0, h["s1"] * d, h["s2"] * d) + h["parity"] * 0.5, "-", lw=1)
                ax[k, c].axvline(np.interp(h["tb"], pts, np.arange(len(pts))), color="r", lw=1)
                ax[k, c].invert_yaxis()
                ax[k, c].set_title(f"jump {k + 1} {name}: t = {h['tb']:.4f} s")
                ax[k, c].set_xlabel("frame")
                ax[k, c].set_ylabel("shoe bottom y (px)")
        ax[0, 0].legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(a.out / f"{a.video.stem}_jumps.png", dpi=80)


if __name__ == "__main__":
    main()
