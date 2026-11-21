"""실험 2 메인 카메라 영상 판독(D-83): 발 디딤 계단으로 위치·통과 시각·걸음을 읽는다.

사용(저장소 맨 위에서): python -I tools/video/read_exp2_video.py <영상> <출력 폴더> [--tiles] [--dump]
화소만 읽는다(컨테이너 태그는 읽지 않는다). 출력: <stem>.json, <stem>_stances.csv, <stem>_xt.png, (--tiles) <stem>_tiles.jpg
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I로 돌리면 스크립트 폴더가 경로에 없다
from vgeom import find_bottles2, red_edge  # noqa: E402

FPS = 60000 / 1001
W, Y0, H = 1920, 380, 340  # 읽는 띠(짝수여야 한다: ffmpeg crop이 색 표본 줄에 맞춰 내림한다)
UP, DOWN = 8, 16           # 발 띠: 붉은 면 바깥 가장자리 기준 위 8 px ~ 아래 16 px
ROWS = np.arange(-UP, DOWN + 1)


def frames(path, sparse_fps=None):
    vf = f"crop={W}:{H}:0:{Y0}"
    if sparse_fps:
        vf = f"fps={sparse_fps}," + vf
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    p.stdout.close()
    p.wait()


def shift_1d(a, b, max_shift=300):
    a = (a - a.mean()) / (a.std() + 1e-9)
    b = (b - b.mean()) / (b.std() + 1e-9)
    best, arg = -9.0, 0
    for s in range(-max_shift, max_shift + 1):
        c = float(np.mean(a[:len(a) - s] * b[s:])) if s >= 0 else float(np.mean(a[-s:] * b[:len(b) + s]))
        if c > best:
            best, arg = c, s
    return arg


def stable_background(video):
    """카메라가 가만히 있던 가장 긴 구간의 프레임 중앙값. → (배경, 시작 s, 끝 s, 어긋남 범위 px)"""
    sp = [f.copy() for f in frames(video, sparse_fps=2)]
    sig = [np.abs(np.diff(f[:150].mean(axis=2).mean(axis=0))) for f in sp]
    dx = np.array([shift_1d(sig[len(sig) // 2], s) for s in sig])
    best = (0, 0, 0)
    for ref in np.unique(dx):
        ok = np.abs(dx - ref) <= 4  # 손떨림 정도(몇 px)는 가만히 있는 것으로 본다
        i = 0
        while i < len(ok):
            if ok[i]:
                j = i
                while j + 1 < len(ok) and ok[j + 1]:
                    j += 1
                if j - i + 1 > best[0]:
                    best = (j - i + 1, i, j)
                i = j + 1
            else:
                i += 1
    _, a, b = best
    bg = np.median(np.stack(sp[a:b + 1:2]), axis=0).astype(np.uint8)
    return bg, a / 2.0, b / 2.0, (int(dx.min()), int(dx.max()))


MS = 8  # 카메라 흔들림 보정 범위(±px)


def band_signals(video, bg, e0, e1):
    """발 띠(가장자리 줄을 따라 편 띠)의 신호. 프레임마다 띠가 배경과 가장 잘 맞는 정수 어긋남(±3 px)을 찾아 맞춘 뒤 잰다.
    → 밝아짐 최대(nfr×W), 변화 최대(nfr×W), 변화 띠(nfr/2×줄×W, uint8), 프레임별 (dy, dx)"""
    x = np.arange(W)
    nr = len(ROWS)
    rows_g = np.arange(-UP - 1 - MS, DOWN + 2 + MS)
    rr = np.clip(np.round((e0 + e1 * x - Y0)[None, :] + rows_g[:, None]).astype(int), 0, H - 1)
    cc = x[None, :]
    big_bg = ndi.uniform_filter(bg[rr, cc].astype(np.float32), size=(3, 3, 1))[1:-1]  # (nr + 2·MS, W, 3)
    bgb = big_bg[MS:MS + nr]
    bgmin = bgb.min(axis=2)
    sub = slice(MS, W - MS, 6)  # 맞춤 오차는 열을 솎아서 잰다
    ref = bgmin[:, sub]
    Sb, Sa, DA, SH = [], [], [], []
    prev = (0, 0)
    for k, f in enumerate(frames(video)):
        big = ndi.uniform_filter(f[rr, cc].astype(np.float32), size=(3, 3, 1))[1:-1]
        bmin = big.min(axis=2)
        def err_at(dy, dx):
            e = np.abs(bmin[MS + dy:MS + dy + nr, MS + dx:W - MS + dx:6] - ref)
            return float(np.sort(e.mean(axis=0))[:int(0.8 * e.shape[1])].mean())  # 사람이 있는 열(큰 오차 20%)은 뺀다

        # 앞 프레임의 어긋남에서 출발해 이웃(±1 px)으로 오차가 줄어드는 쪽을 따라간다(흔들림은 이어진다)
        cur = (err_at(*prev), prev[0], prev[1])
        z = err_at(0, 0)
        if z <= cur[0]:
            cur = (z, 0, 0)
        for _ in range(MS):
            moved = False
            for ddy, ddx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = cur[1] + ddy, cur[2] + ddx
                if abs(ny) > MS or abs(nx) > MS:
                    continue
                e = err_at(ny, nx)
                if e < cur[0] - 1e-4:
                    cur, moved = (e, ny, nx), True
            if not moved:
                break
        if cur[0] > 0.92 * z:  # 어긋남 없이도 거의 같게 맞으면 움직이지 않은 것으로 본다(가만한 영상에서 헛보정을 막는다)
            cur = (z, 0, 0)
        best = cur
        prev = (cur[1], cur[2])
        _, dy, dx = best
        band = np.roll(big[MS + dy:MS + dy + nr], -dx, axis=1)
        diff = band - bgb
        diff -= np.median(diff[:, ::6], axis=(0, 1))  # 프레임 전체의 밝기 변화(노출)는 색마다 중앙값으로 뺀다
        dany = np.abs(diff).max(axis=2)
        db = (band - np.median((band - bgb)[:, ::6], axis=(0, 1))).min(axis=2) - bgmin
        if dx:
            edge = slice(0, abs(dx) + 1) if dx < 0 else slice(W - dx - 1, W)
            dany[:, edge] = 0
            db[:, edge] = 0
        Sb.append(db.max(axis=0).astype(np.float16))
        Sa.append(dany.max(axis=0).astype(np.float16))
        SH.append((dy, dx))
        if k % 2 == 0:
            DA.append(np.clip(dany, 0, 255).astype(np.uint8))
    return np.array(Sb, np.float32), np.array(Sa, np.float32), np.array(DA), np.array(SH)


def debase(S):
    """열마다 느리게 변하는 바탕(2 s 토막의 아래 25% 값, 토막 사이는 선형 보간)을 뺀다. 카메라가 조금 움직여 생긴 가만한 신호를 없앤다."""
    nfr = len(S)
    nb = int(2 * FPS)
    starts = np.arange(0, nfr, nb)
    tc = np.array([(s + min(s + nb, nfr)) / 2 for s in starts])
    bv = np.array([np.percentile(S[s:s + nb], 25, axis=0) for s in starts])
    if len(tc) < 2:
        return S - bv[0]
    k = np.arange(nfr)
    seg = np.clip(np.searchsorted(tc, k) - 1, 0, len(tc) - 2)
    w = np.clip((k - tc[seg]) / (tc[seg + 1] - tc[seg]), 0, 1)[:, None]
    return S - (bv[seg] * (1 - w) + bv[seg + 1] * w)


def stance_blobs(S, hi, lo, min_s):
    """x–t에서 같은 x에 min_s 이상 머문 신호 덩어리(디딤 후보). → [시작 s, 끝 s, x, 화소 수]"""
    n = max(int(round(min_s * FPS)), 3)
    P = ndi.binary_opening(S > lo, structure=np.ones((n, 1), bool))
    P = ndi.binary_closing(P, structure=np.ones((3, 3), bool))
    lab, m = ndi.label(P, structure=np.ones((3, 3), bool))
    if m == 0:
        return np.zeros((0, 4))
    mx = ndi.maximum(S, lab, range(1, m + 1))
    out = []
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        if mx[i - 1] < hi:
            continue
        sub = lab[sl] == i
        ww = sl[1].stop - sl[1].start
        if 3 <= ww <= 60 and sub.sum() >= 3 * n:
            xc = np.nonzero(sub)[1]
            out.append([sl[0].start / FPS, (sl[0].stop - 1) / FPS, float(np.median(xc)) + sl[1].start, float(sub.sum())])
    return np.array(sorted(out)) if out else np.zeros((0, 4))


def find_chain(B, use=None):
    """디딤 후보 가운데 한 사람의 걸음 줄(같은 속도로 x가 한쪽으로 가는 것)을 고른다. → (고른 것의 번호, 방향 부호)"""
    t, x = B[:, 0], B[:, 2]
    use = np.ones(len(B), bool) if use is None else use
    best = (0, None, 0.0)
    for i in np.flatnonzero(use):
        dt = t - t[i]
        for j in np.flatnonzero(use & (dt > 2.0) & (dt < 20.0)):
            v = (x[j] - x[i]) / dt[j]
            if not 25 <= abs(v) <= 500:
                continue
            inl = use & (np.abs(x - (x[i] + v * (t - t[i]))) < 30)
            c = int(inl.sum())
            if c > best[0]:
                best = (c, inl, v)
    if best[1] is None:
        return np.zeros(0, int), 0
    inl, v = best[1], best[2]
    for tol in (40, 28, 22):  # 속도가 조금 변하는 것을 3차식으로 따라가며 다시 고른다
        if inl.sum() < 6:
            break
        c = np.polyfit(t[inl], x[inl], 3 if inl.sum() >= 10 else 1)
        lo_t, hi_t = t[inl].min() - 2.5, t[inl].max() + 2.5
        inl = use & (np.abs(x - np.polyval(c, t)) < tol) & (t >= lo_t) & (t <= hi_t)
    return np.flatnonzero(inl), (1 if v > 0 else -1)


def clean_chain(C, sgn):
    """같은 자리 조각을 합치고, 자리 순서가 어긋난 것을 버리고, 한 걸음 빠진 틈을 채운다. → ([시작, 끝, x, 화소 수, 채움], 걸음 간격, 걸음 px)"""
    C = C[np.argsort(C[:, 2] * sgn)]
    merged = [C[0].copy()]
    for s in C[1:]:
        p = merged[-1]
        if abs(s[2] - p[2]) < 10:
            w0, w1 = p[3], s[3]
            merged[-1] = np.array([min(p[0], s[0]), max(p[1], s[1]), (p[2] * w0 + s[2] * w1) / (w0 + w1), w0 + w1])
        else:
            merged.append(s.copy())
    C = np.array(merged)
    C = C[np.argsort(C[:, 0])]
    C = C[C[:, 3] >= 0.35 * np.median(C[:, 3])]
    keep = np.ones(len(C), bool)
    last = 0
    for i in range(1, len(C)):
        if (C[i, 2] - C[last, 2]) * sgn <= 6:
            keep[i] = False
        else:
            last = i
    C = C[keep]
    iv, dx = np.diff(C[:, 0]), np.diff(C[:, 2]) * sgn
    miv, mdx = float(np.median(iv)), float(np.median(dx))
    rows = [list(s) + [0.0] for s in C]
    for i in range(len(C) - 1):  # 걸음이 빠진 틈: 시간과 거리가 모두 같은 배수(2–6)면 그만큼 고르게 채우고 표시한다
        r_t, r_x = iv[i] / miv, dx[i] / mdx
        m = int(round(r_t))
        if 2 <= m <= 6 and abs(r_t - m) < 0.3 * m ** 0.5 and abs(r_x - m) < 0.3 * m ** 0.5:
            for q in range(1, m):
                rows.append([C[i, 0] + (C[i + 1, 0] - C[i, 0]) * q / m, np.nan, C[i, 2] + (C[i + 1, 2] - C[i, 2]) * q / m, 0.0, 1.0])
    return np.array(sorted(rows)), miv, mdx


def cross_time(ST, xb, sgn):
    """디딤 시작점 (t, x)를 이은 꺾은선이 x = xb를 지나는 시각(범위 밖이면 끝의 두 점으로 늘인다)."""
    o = np.argsort(ST[:, 2] * sgn)
    xs, ts = ST[o, 2] * sgn, ST[o, 0]
    v = xb * sgn
    if v <= xs[0]:
        return float(ts[0] + (v - xs[0]) * (ts[1] - ts[0]) / (xs[1] - xs[0])), True
    if v >= xs[-1]:
        return float(ts[-1] + (v - xs[-1]) * (ts[-1] - ts[-2]) / (xs[-1] - xs[-2])), True
    return float(np.interp(v, xs, ts)), False


def sole_height(DA, s):
    """디딤 가운데 구간의 변화량 세로 분포에서 반값 높이(가장자리 줄 기준 아래 px). DA는 한 프레임 건너 저장."""
    if not np.isfinite(s[1]):
        return np.nan
    k0, k1, xc = int(round(s[0] * FPS / 2)), int(round(s[1] * FPS / 2)), int(round(s[2]))
    ka, kb = k0 + int(0.25 * (k1 - k0)), k0 + int(0.75 * (k1 - k0)) + 1
    c0, c1 = max(xc - 2, 0), min(xc + 3, W)
    if kb - ka < 3 or k0 < 26:
        return np.nan
    prof = DA[ka:kb, :, c0:c1].astype(np.float32).mean(axis=(0, 2))
    base = DA[k0 - 24:k0 - 6, :, c0:c1].astype(np.float32).mean(axis=(0, 2))  # 발이 오기 전 같은 자리
    e = prof - base
    top = np.median(e[(ROWS >= -3) & (ROWS <= 0)])
    if top < 20:
        return np.nan
    half = 0.5 * top
    for i in range(len(ROWS) - 2, 0, -1):
        if e[i] >= half and e[i + 1] < half:
            return float(ROWS[i] + (e[i] - half) / (e[i] - e[i + 1]))
    return np.nan


THR = {"bright": (25.0, 14.0), "any": (80.0, 40.0)}  # (씨앗 문턱, 덩어리 문턱)


def prepare(S, mode):
    """바탕을 빼고, 변화 신호(any)는 x로 넓은 것(몸 그림자, 가까이 지나가는 사람)을 없앤다(27 px 열기 연산을 뺀다)."""
    S = debase(S)
    if mode == "any":
        S = S - ndi.grey_opening(S, size=(1, 27))
    return S


def evaluate(ST, sgn, miv, mdx, xA, xB):
    tA, exA = cross_time(ST, xA, sgn)
    tB, exB = cross_time(ST, xB, sgn)
    t_in, t_out = min(tA, tB), max(tA, tB)
    iv, dx = np.diff(ST[:, 0]), np.diff(ST[:, 2]) * sgn
    sect = (ST[:-1, 0] >= t_in - 1.0) & (ST[1:, 0] <= t_out + 1.0)
    irr = np.flatnonzero(sect & ((iv > 1.4 * miv) | (iv < 0.65 * miv) | (dx > 1.5 * mdx) | (dx < 0.55 * mdx)))
    ins = (ST[:, 0] >= t_in) & (ST[:, 0] < t_out)
    score = int(ins.sum()) - 3 * len(irr) - 2 * int(ST[ins, 4].sum()) - (50 if exA or exB else 0)
    return dict(ST=ST, sgn=sgn, miv=miv, mdx=mdx, tA=tA, tB=tB, ex=(exA, exB), irr=irr, ins=ins, score=score)


def analyse(S, mode, xA, xB):
    """한 신호에서 걸음 줄 후보를 셋까지 찾아 가장 고른 것을 낸다(지나가는 다른 사람의 줄을 고르지 않게)."""
    hi, lo = THR[mode]
    S = prepare(S, mode)
    B0 = stance_blobs(S, hi, lo, 0.10)
    best = None
    use = np.ones(len(B0), bool)
    for _ in range(3):
        idx, sgn = find_chain(B0, use)
        if len(idx) < 8:
            break
        use[idx] = False
        miv0 = float(np.median(np.diff(np.sort(B0[idx, 0]))))
        B = stance_blobs(S, hi, lo, float(np.clip(0.30 * miv0, 0.07, 0.25)))  # 걸음 간격에 맞춘 머무는 시간으로 다시
        near = np.zeros(len(B), bool)  # 같은 줄: 처음 고른 디딤들 가까이(시간 0.6 s, 자리 45 px) 있는 것만
        for q in B0[idx]:
            near |= (np.abs(B[:, 0] - q[0]) < 0.6) & (np.abs(B[:, 2] - q[2]) < 45)
        idx2, sgn2 = find_chain(B, near)
        if len(idx2) < 8:
            continue
        ST, miv, mdx = clean_chain(B[idx2], sgn2)
        if len(ST) < 8:
            continue
        r = evaluate(ST, sgn2, miv, mdx, xA, xB)
        if best is None or r["score"] > best["score"]:
            best = r
    if best is not None:
        best["S"] = S
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--tiles", action="store_true")
    ap.add_argument("--dump", action="store_true", help="발 띠 신호를 npz로 남긴다(조정용)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    stem = a.video.stem
    R = {"video": a.video.name, "fps": FPS, "thresholds": THR, "flags": []}

    bg, ts0, ts1, dxr = stable_background(a.video)
    Image.fromarray(bg).save(a.out / f"{stem}_bg.png")
    e0, e1, esd, en = red_edge(bg, Y0)
    bot, peaks = find_bottles2(bg, Y0, e0, e1)
    if bot is None:
        raise SystemExit(f"물병 둘을 못 찾음: 가장자리 줄 위의 밝은 물체 {peaks}")
    (xA, cA), (xB, cB), bflags = bot
    R["flags"] += bflags
    R.update(camera_shift_px_range=list(dxr), t_stable_from_s=ts0, t_stable_to_s=ts1, edge=[e0, e1], edge_resid_sd_px=esd,
             bottle_A_x=xA, bottle_B_x=xB, bottle_contrast=[cA, cB], edge_objects=peaks)

    Sb, Sa, DA, SH = band_signals(a.video, bg, e0, e1)
    R["shake_frames_frac"] = float((np.abs(SH).sum(axis=1) > 0).mean())
    R["shake_max_px"] = [int(np.abs(SH[:, 0]).max()), int(np.abs(SH[:, 1]).max())]
    nfr = len(Sb)
    R["frames"] = nfr
    if a.dump:
        np.savez_compressed(a.out / f"{stem}_S.npz", Sb=Sb.astype(np.float16), Sa=Sa.astype(np.float16), xA=xA, xB=xB)
    res = {}
    for mode, S in (("bright", Sb), ("any", Sa)):
        r = analyse(S, mode, xA, xB)
        if r is not None:
            res[mode] = r
    if not res:
        (a.out / f"{stem}.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
        raise SystemExit("걸음 줄을 못 찾음")
    mode = max(res, key=lambda m: res[m]["score"])
    r = res[mode]
    S, ST, sgn, ins, irr = r["S"], r["ST"], r["sgn"], r["ins"], r["irr"]
    t_in, t_out = min(r["tA"], r["tB"]), max(r["tA"], r["tB"])
    core = ins[:-1] & ins[1:]
    iv = np.diff(ST[:, 0])
    R.update(mode=mode, mode_scores={m: res[m]["score"] for m in res}, direction="→" if sgn > 0 else "←",
             t_cross_A_s=r["tA"], t_cross_B_s=r["tB"], t_in_app_s=t_in, t_out_app_s=t_out, dt_app_s=t_out - t_in,
             n_stances=int(len(ST)), filled_at_s=[round(float(x), 2) for x in ST[ST[:, 4] > 0, 0]],
             step_interval_median_s=r["miv"], step_px_median=r["mdx"],
             step_interval_in_section_s=[float(np.median(iv[core])), float(iv[core].min()), float(iv[core].max())] if core.sum() > 3 else None,
             cadence_video_spm=60 / float(np.median(iv[core])) if core.sum() > 3 else None,
             cadence_mean_spm=float(60 * (ins.sum() - 1) / (ST[ins, 0].max() - ST[ins, 0].min())) if ins.sum() > 3 else None,
             contacts_in_apparent_window=int(ins.sum()), irregular_at_s=[round(float(ST[i, 0]), 2) for i in irr])
    if len(irr):
        R["flags"].append("irregular_steps")
    if r["ex"][0] or r["ex"][1]:
        R["flags"].append("crossing_extrapolated")
    if t_in < ts0 or t_out > ts1 + 0.5:
        R["flags"].append("camera_moving_during_section")

    sole = np.array([sole_height(DA, s) for s in ST])
    okd = ins & np.isfinite(sole)
    if okd.sum() >= 6:
        c = np.polyfit(ST[okd, 2], sole[okd], 1)
        rs = sole[okd] - np.polyval(c, ST[okd, 2])
        kp = np.abs(rs) < 2.5 * max(rs.std(), 0.3)
        c = np.polyfit(ST[okd, 2][kp], sole[okd][kp], 1)
        rs = sole[okd][kp] - np.polyval(c, ST[okd, 2][kp])
        R.update(delta_px_at_A=float(np.polyval(c, xA)), delta_px_at_B=float(np.polyval(c, xB)),
                 delta_px_mean=float(np.polyval(c, (xA + xB) / 2)), delta_px_resid_sd=float(rs.std()), delta_n=int(kp.sum()))
    else:
        R["flags"].append("no_delta")

    out = np.column_stack([ST, sole])
    np.savetxt(a.out / f"{stem}_stances.csv", out, delimiter=",", fmt="%.4f", comments="",
               header="t_contact_s,t_off_s,x_px,pixels,filled,sole_below_edge_px")
    (a.out / f"{stem}.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")

    k0, k1 = max(int((t_in - 3) * FPS), 0), min(int((t_out + 3) * FPS), nfr)
    fig, ax = plt.subplots(1, 1, figsize=(22, 10))
    ax.imshow(np.clip(S[k0:k1], 0, 70).T, aspect="auto", origin="lower", cmap="gray_r", extent=[k0 / FPS, k1 / FPS, 0, W], interpolation="nearest")
    for s in ST:
        col = "magenta" if s[4] else ("lime" if t_in <= s[0] < t_out else "orange")
        if np.isfinite(s[1]):
            ax.plot([s[0], s[1]], [s[2], s[2]], color=col, lw=1.5)
        ax.plot(s[0], s[2], "mx" if s[4] else "r.", ms=6)
    ax.axvline(t_in, color="r", lw=0.6)
    ax.axvline(t_out, color="r", lw=0.6)
    ax.axhline(xA, color="r", lw=0.4)
    ax.axhline(xB, color="r", lw=0.4)
    lo_x, hi_x = sorted([np.interp(k0 / FPS, ST[:, 0], ST[:, 2]), np.interp(k1 / FPS, ST[:, 0], ST[:, 2])])
    ax.set_ylim(max(lo_x - 120, 0), min(hi_x + 120, W))
    ax.set_title(f"{stem} [{mode}] {R['direction']} dt_app {t_out - t_in:.3f} s, contacts {int(ins.sum())}, flags {R['flags']}")
    fig.tight_layout()
    fig.savefig(a.out / f"{stem}_xt.png", dpi=72)
    plt.close(fig)

    if a.tiles:  # 디딤이 시작된 프레임(2프레임 뒤)의 발 주변을 잘라 이어 붙인다: 눈으로 세어 볼 때 쓴다
        sel = ST[(ST[:, 0] >= t_in - 1.5) & (ST[:, 0] < t_out + 1.5)]
        tiles = []
        for s in sel:
            x0 = int(np.clip(s[2] - 40, 0, W - 80))
            y0 = int(e0 + e1 * s[2]) - 52
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s[0] + 2 / FPS:.4f}", "-i", str(a.video), "-vf",
                                  f"crop=80:72:{x0}:{y0 // 2 * 2}", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True).stdout
            if len(raw) < 80 * 72 * 3:
                continue
            im = Image.fromarray(np.frombuffer(raw, np.uint8).reshape(72, 80, 3)).resize((160, 144), Image.LANCZOS)
            d = ImageDraw.Draw(im)
            d.text((2, 1), f"{s[0]:.2f}" + ("*" if s[4] else ""), fill=(255, 255, 0) if t_in <= s[0] < t_out else (255, 140, 0))
            d.line([((s[2] - x0) * 2, 120), ((s[2] - x0) * 2, 143)], fill=(0, 255, 0))
            tiles.append(im)
        per = 12
        sheet = Image.new("RGB", (160 * per, 144 * ((len(tiles) + per - 1) // per)))
        for i, im in enumerate(tiles):
            sheet.paste(im, (160 * (i % per), 144 * (i // per)))
        sheet.save(a.out / f"{stem}_tiles.jpg", quality=88)

    show = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in R.items() if k not in ("edge_objects", "edge")}
    print(json.dumps(show, ensure_ascii=False))


if __name__ == "__main__":
    main()
