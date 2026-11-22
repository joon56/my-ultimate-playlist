"""굽힌 다리 진자 영상의 마커 추적 결과에서 무릎 굽힘 각을 읽고 video_markers.csv에 넣을 줄을 만든다.

사용: python -I tools/video/knee_read.py <출력 폴더> <stem> [...] [--ratio 0.25] [--drop 0.28] [--hip hybrid|red|circle] [--plot]

방법
1. 정강이 축 = 노랑(발목 위 테이프) → 파랑(무릎 아래 테이프). 튄 프레임(방향이 앞뒤 7프레임 중앙값에서 3° 넘게, 거리가
   중앙값에서 5% 넘게 벗어남)은 뺀다.
2. 무릎 관절 점 K = 파랑에서 정강이 축을 따라 ratio × (노랑–파랑 거리)만큼 올린 점. 파란 테이프가 관절선 아래에 있어서다.
3. 엉덩관절 점 C(영상마다 하나). 높이 = 빨간 테이프 중심의 중앙값에서 화면 아래로 drop × (노랑–파랑 거리)만큼 내린 곳(빨간
   테이프가 허리띠 높이라 엉덩관절보다 위에 있다). 좌우 자리 = 그 높이에 중심을 둔 원이 K(t)의 호에 가장 잘 맞는 곳(hybrid, 기본).
   견주어 보는 용도로 --hip red(좌우도 빨간 테이프 중앙값), --hip circle(높이까지 호에 맞춘 원의 중심: 호가 짧아 영상마다 크게
   달라진다)이 있다.
4. 굽힘 각 = 180° − (K에서 본 C와 노랑 사이 각). '이어진 흔들림'(swing_read의 극대 줄) 구간에서 본다. 평균은 추적이 빠진
   프레임을 시간으로 이어 붙인 뒤 주기마다 낸 평균의 평균(0.35 s보다 긴 틈이 있는 주기는 뺀다).
5. 기록지 줄: 틈이 길지 않은 주기마다 같은 간격으로 6개, 가장 가까운 쓸 수 있는 프레임(±3프레임)의 C·K·노랑 좌표.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).resolve().parent))
import swing_read as sr  # noqa: E402

ROWS_PER_CYCLE = 6


def clean(z, t0: float, t1: float):
    t, Y, B, H = z["t"], z["yellow"], z["blue"], z["red"]
    idx = np.flatnonzero(np.isfinite(B[:, 0]) & np.isfinite(Y[:, 0]) & (t >= t0) & (t <= t1))
    r = B[idx] - Y[idx]
    d = np.hypot(r[:, 0], r[:, 1])
    ang = np.unwrap(np.arctan2(r[:, 1], r[:, 0]))
    ok = (np.abs(np.degrees(ang - median_filter(ang, size=7, mode="nearest"))) < 3) & (np.abs(d - np.median(d)) < 0.05 * np.median(d))
    idx = idx[ok]
    return idx, t[idx], Y[idx], B[idx], H[idx]


def circle(K: np.ndarray):
    res = lambda p: np.hypot(K[:, 0] - p[0], K[:, 1] - p[1]) - p[2]
    best = None
    for sgn in (-1, 1):  # 중심이 위쪽이라고 가정하지 않는다(영상이 돌아가 있을 수 있다)
        for ax in (0, 1):
            c0 = K.mean(axis=0).copy()
            c0[ax] += sgn * 450
            s = least_squares(res, [c0[0], c0[1], 450.0])
            rms = float(np.sqrt(np.mean(s.fun ** 2)))
            if best is None or rms < best[1]:
                best = (s.x, rms)
    return best


def flexion(C, K, Y):
    a, b = C - K, Y - K
    cosv = (a * b).sum(axis=1) / (np.hypot(a[:, 0], a[:, 1]) * np.hypot(b[:, 0], b[:, 1]))
    return 180.0 - np.degrees(np.arccos(np.clip(cosv, -1, 1)))


def analyse(out: Path, stem: str, ratio: float, drop: float = 0.28, hip: str = "hybrid"):
    z = np.load(out / f"{stem}_markers.npz")
    t_all, s = sr.series(z)
    tp = sr.chain(sr.extremes(t_all, s, 1))
    t0, t1 = float(tp[0]), float(tp[-1])
    idx, t, Y, B, H = clean(z, t0, t1)
    r = B - Y
    d = np.hypot(r[:, 0], r[:, 1])
    u = r / d[:, None]
    K = B + ratio * float(np.median(d)) * u
    (ccx, ccy, rad), rms = circle(K)
    hmed = np.nanmedian(H, axis=0)
    cy = float(hmed[1]) + drop * float(np.median(d))
    if hip == "circle":
        cx, cy = ccx, ccy
    elif hip == "red":
        cx = float(hmed[0])
    else:  # hybrid: 높이는 빨간 테이프에서, 좌우 자리는 그 높이에 중심을 둔 원이 K(t)의 호에 가장 잘 맞는 곳
        fit = least_squares(lambda p: np.hypot(K[:, 0] - p[0], K[:, 1] - cy) - p[1], [float(hmed[0]), 400.0])
        cx = float(fit.x[0])
    C = np.array([cx, cy])
    fl = flexion(C[None, :], K, Y)
    # 주기 위상이 고르게 들어가도록: 주기마다 평균을 낸 뒤 주기들의 평균
    # 추적이 빠진 프레임 때문에 위상이 치우치지 않게, 1/60 s 격자로 이어 붙인 뒤(0.35 s보다 긴 틈이 있는 주기는 뺀다) 주기마다 평균
    grid = np.arange(t0, t1, 1 / 60)
    flg = np.interp(grid, t, fl)
    gap = np.array([np.min(np.abs(t - g)) for g in grid])
    cyc = np.searchsorted(tp, grid, side="right") - 1
    whole = [k for k in range(len(tp) - 1) if (cyc == k).sum() >= 10 and gap[cyc == k].max() <= 0.175]  # 틈이 길지 않은 주기
    per = [float(flg[cyc == k].mean()) for k in whole]
    info = dict(stem=stem, ratio=ratio, drop=drop, hip=hip, t0=t0, t1=t1, n_frames=int(len(idx)), n_cycles=len(per),
                tape_dist_px=float(np.median(d)), delta_px=ratio * float(np.median(d)), drop_px=drop * float(np.median(d)),
                hip_center=[float(cx), float(cy)], thigh_px=float(np.median(np.hypot(K[:, 0] - cx, K[:, 1] - cy))),
                circle_center=[float(ccx), float(ccy)], thigh_radius_px=float(rad), circle_rms_px=rms,
                red_median=[float(hmed[0]), float(hmed[1])], red_sd=[float(np.nanstd(H[:, 0])), float(np.nanstd(H[:, 1]))],
                flexion_mean_of_cycles=float(np.mean(per)), flexion_sd_between_cycles=float(np.std(per, ddof=1)) if len(per) > 1 else None,
                flexion_first3=float(np.mean(per[:3])), flexion_last3=float(np.mean(per[-3:])),
                flexion_p5_p95=[float(np.percentile(fl, 5)), float(np.percentile(fl, 95))])
    rows = []
    ticks = np.concatenate([np.arange(tp[k], tp[k + 1] - 1e-9, (tp[k + 1] - tp[k]) / ROWS_PER_CYCLE) for k in whole]) if whole else []
    for tt in ticks:  # 틈이 길지 않은 주기마다 같은 간격으로 ROWS_PER_CYCLE개(위상이 고르게 들어간다)
        j = int(np.argmin(np.abs(t - tt)))
        if abs(t[j] - tt) <= 3.5 / 60:
            rows.append(dict(event_no=len(rows) + 1, frame_no=int(idx[j]), t=float(t[j]), hip=(float(cx), float(cy)),
                             knee=(float(K[j, 0]), float(K[j, 1])), ankle=(float(Y[j, 0]), float(Y[j, 1])),
                             blue=(float(B[j, 0]), float(B[j, 1])), flexion=float(fl[j])))
    info["rows_mean_flexion"] = float(np.mean([r["flexion"] for r in rows])) if rows else None
    info["n_rows"] = len(rows)
    return info, rows, (t, fl, tp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("stems", nargs="+")
    ap.add_argument("--ratio", type=float, default=0.25)
    ap.add_argument("--drop", type=float, default=0.28)
    ap.add_argument("--hip", choices=("hybrid", "red", "circle"), default="hybrid")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--no-save", action="store_true", help="결과 파일을 쓰지 않는다(민감도 확인용)")
    a = ap.parse_args()
    allres = {}
    for stem in a.stems:
        info, rows, (t, fl, tp) = analyse(a.out, stem, a.ratio, a.drop, a.hip)
        allres[stem] = dict(info=info, rows=rows)
        sd = info["flexion_sd_between_cycles"]
        print(f"{stem:<8} 올림 {a.ratio:.2f} 내림 {a.drop:.2f} hip={a.hip} | 구간 {info['t0']:.1f}–{info['t1']:.1f} s, 프레임 {info['n_frames']}, "
              f"주기 {info['n_cycles']} | 테이프 거리 {info['tape_dist_px']:.0f} px | hip ({info['hip_center'][0]:.0f}, {info['hip_center'][1]:.0f}), "
              f"허벅지 {info['thigh_px']:.0f} px | 빨강 ({info['red_median'][0]:.0f}, {info['red_median'][1]:.0f}) SD ({info['red_sd'][0]:.0f}, "
              f"{info['red_sd'][1]:.0f}) | 호 중심 ({info['circle_center'][0]:.0f}, {info['circle_center'][1]:.0f}) 반지름 {info['thigh_radius_px']:.0f} "
              f"잔차 {info['circle_rms_px']:.1f} | 굽힘 평균 {info['flexion_mean_of_cycles']:.1f}° (주기 사이 SD {float('nan') if sd is None else sd:.1f}, "
              f"처음 3주기 {info['flexion_first3']:.1f}, 끝 3주기 {info['flexion_last3']:.1f}, 5–95% {info['flexion_p5_p95'][0]:.0f}–"
              f"{info['flexion_p5_p95'][1]:.0f}) | 줄 {info['n_rows']}개 평균 {info['rows_mean_flexion']:.1f}°")
        if a.plot:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(13, 3))
            ax.plot(t, fl, ".", ms=2)
            for x in tp:
                ax.axvline(x, color="r", lw=0.5)
            ax.set_title(f"{stem}: knee flexion (deg), ratio {a.ratio}, drop {a.drop}, hip {a.hip}")
            fig.tight_layout()
            fig.savefig(a.out / f"{stem}_knee.png", dpi=70)
            plt.close(fig)
    if not a.no_save:
        (a.out / f"knee_results_{a.ratio:.2f}.json").write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding="utf-8")
