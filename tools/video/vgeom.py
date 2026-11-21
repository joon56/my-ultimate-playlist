"""배경 영상에서 붉은 트랙 면의 바깥 가장자리 줄과 그 위의 물병 둘을 찾는다(D-83). 좌표는 전체 화면(px)."""
import numpy as np
from scipy import ndimage as ndi

W = 1920


def red_edge(bg, y0):
    """→ (e0, e1, 잔차 표준편차, 쓴 띠 수): 가장자리 y = e0 + e1 x. 세로 띠마다 맨 위의 긴 붉은 구간이 시작되는 높이(R−G 반값)."""
    rg = ndi.uniform_filter(bg[..., 0].astype(np.float32) - bg[..., 1], size=(1, 9))
    H = bg.shape[0]
    xs, ys = [], []
    for x0 in range(40, W - 40, 16):
        prof = rg[:, x0:x0 + 16].mean(axis=1)
        red = prof > 10
        run, start, top = 0, None, None
        for r in range(H):  # 맨 위에서부터 15줄 이상 이어진 첫 붉은 구간
            if red[r]:
                if run == 0:
                    start = r
                run += 1
                if run >= 15:
                    top = start
                    break
            else:
                run = 0
        if top is None or top < 12 or top + 14 >= H:
            continue
        lo, hi = np.median(prof[top - 12:top - 3]), np.median(prof[top + 5:top + 14])
        if hi - lo < 8:
            continue
        half = (lo + hi) / 2
        k = top - 6 + np.flatnonzero((prof[top - 6:top + 6] < half) & (prof[top - 5:top + 7] >= half))
        if not len(k):
            continue
        k = int(k[0])
        xs.append(x0 + 8)
        ys.append(y0 + k + (half - prof[k]) / (prof[k + 1] - prof[k]))
    xs, ys = np.array(xs, float), np.array(ys, float)
    keep = np.ones(len(xs), bool)
    c = np.polyfit(xs, ys, 1)
    for _ in range(8):
        res = ys - np.polyval(c, xs)
        keep = np.abs(res - np.median(res[keep])) < max(1.2, 2.5 * np.std(res[keep]))
        c = np.polyfit(xs[keep], ys[keep], 1)
    res = ys[keep] - np.polyval(c, xs[keep])
    return float(c[1]), float(c[0]), float(res.std()), int(keep.sum())


def find_bottles(bg, y0, e0, e1):
    """가장자리 줄을 따라 주변보다 밝은 작은 물체 둘(1200–1600 px 떨어진 가장 뚜렷한 쌍). → [(x, 뚜렷함), (x, 뚜렷함)]"""
    mn = bg.min(axis=2).astype(np.float32)
    H = bg.shape[0]
    x = np.arange(W)
    rows = np.arange(-12, 3)
    rr = np.clip(np.round((e0 + e1 * x - y0)[None, :] + rows[:, None]).astype(int), 0, H - 1)
    strip = mn[rr, x[None, :]]                       # (15, W): 가장자리 위 12줄 ~ 아래 2줄
    col = strip.max(axis=0)
    prof = col - ndi.median_filter(col, size=81)     # 옆으로 길게 밝은 것(선·배수로)은 빠진다
    prof = ndi.uniform_filter1d(prof, 3)
    pk = [i for i in range(20, W - 20) if prof[i] > 15 and prof[i] == prof[i - 8:i + 9].max()]
    best = None
    for i in pk:
        for j in pk:
            if 1300 < j - i < 1500:
                sc = prof[i] + prof[j]
                if best is None or sc > best[0]:
                    best = (sc, i, j)
    if best is None:
        return None, [(int(i), round(float(prof[i]), 1)) for i in pk]
    out = []
    for i in best[1:]:
        w = np.clip(prof[i - 4:i + 5], 0, None)
        out.append((float((np.arange(i - 4, i + 5) * w).sum() / w.sum()), float(prof[i])))
    return out, [(int(i), round(float(prof[i]), 1)) for i in pk]


def edge_signature(bg, y0, e0, e1):
    """가장자리 줄 위 20–100 px(벽과 관중석 아래쪽)의 세로 경계 무늬. 클립끼리 가로로 맞추는 데 쓴다. → 길이 W−1"""
    H = bg.shape[0]
    x = np.arange(W)
    rows = np.arange(-100, -19)
    rr = np.clip(np.round((e0 + e1 * x - y0)[None, :] + rows[:, None]).astype(int), 0, H - 1)
    g = bg.astype(np.float32).mean(axis=2)[rr, x[None, :]]
    return ndi.uniform_filter1d(np.abs(np.diff(g, axis=1)).mean(axis=0), 3)


def register_x(sig, ref, lo, hi, max_shift=380):
    """ref의 [lo, hi) 구간 무늬가 sig에서 얼마나 옆으로 가 있는지(px). → (어긋남, 상관)"""
    a = ref[lo:hi]
    a = (a - a.mean()) / (a.std() + 1e-9)
    best, arg = -9.0, 0
    for sft in range(-max_shift, max_shift + 1):
        l, h = lo + sft, hi + sft
        if l < 0 or h > len(sig):
            continue
        b = sig[l:h]
        c = float(np.mean(a * (b - b.mean()) / (b.std() + 1e-9)))
        if c > best:
            best, arg = c, sft
    return arg, best


def bottles_by_reference(bg, y0, e0, e1, ref):
    """기준 클립의 물병 자리를 무늬 맞춤으로 옮기고, 가까이(±12 px)에 밝은 봉우리가 있으면 거기에 맞춘다.
    ref = dict(sig, xA, xB). → ((xA, 봉우리 있음), (xB, 봉우리 있음), 맞춤 정보)"""
    sig = edge_signature(bg, y0, e0, e1)
    out, info = [], {}
    mn = bg.min(axis=2).astype(np.float32)
    H = bg.shape[0]
    x = np.arange(W)
    rows = np.arange(-12, 3)
    rr = np.clip(np.round((e0 + e1 * x - y0)[None, :] + rows[:, None]).astype(int), 0, H - 1)
    col = mn[rr, x[None, :]].max(axis=0)
    prof = ndi.uniform_filter1d(col - ndi.median_filter(col, size=81), 3)
    for name, xr in (("A", ref["xA"]), ("B", ref["xB"])):
        lo, hi = int(max(xr - 330, 0)), int(min(xr + 330, W - 1))
        sft, cor = register_x(sig, ref["sig"], lo, hi)
        xp = xr + sft
        info[name] = dict(shift=int(sft), corr=round(cor, 3))
        if not 6 <= xp <= W - 7:
            out.append((float("nan"), False))
            continue
        a, b = int(max(xp - 12, 4)), int(min(xp + 13, W - 5))
        i = a + int(np.argmax(prof[a:b]))
        if prof[i] > 8:
            w = np.clip(prof[i - 4:i + 5], 0, None)
            out.append((float((np.arange(i - 4, i + 5) * w).sum() / w.sum()), True))
        else:
            out.append((float(xp), False))
        info[name]["peak"] = round(float(prof[i]), 1)
    return out[0], out[1], info


GAP, GAP_TOL = 1411.0, 15.0  # 두 물병의 화면 간격(px): 둘 다 잡힌 클립들에서 1405–1417


def find_bottles2(bg, y0, e0, e1):
    """가장자리 줄 위의 밝은 물체 가운데 간격이 GAP인 쌍을 찾는다. 왼쪽 물병이 흐려 안 잡히면 오른쪽에서 GAP만큼 뺀 자리를 쓴다.
    → ((xA, 뚜렷함), (xB, 뚜렷함), 표시 목록, 봉우리 목록) 또는 None"""
    mn = bg.min(axis=2).astype(np.float32)
    H = bg.shape[0]
    x = np.arange(W)
    rows = np.arange(-12, 3)
    rr = np.clip(np.round((e0 + e1 * x - y0)[None, :] + rows[:, None]).astype(int), 0, H - 1)
    col = mn[rr, x[None, :]].max(axis=0)
    prof = ndi.uniform_filter1d(col - ndi.median_filter(col, size=81), 3)
    pk = [i for i in range(20, W - 20) if prof[i] > 5 and prof[i] == prof[i - 8:i + 9].max()]
    peaks = [(int(i), round(float(prof[i]), 1)) for i in pk if prof[i] > 15]

    def centre(i):
        w = np.clip(prof[i - 4:i + 5], 0, None)
        return float((np.arange(i - 4, i + 5) * w).sum() / w.sum())

    best = None
    for j in pk:
        if prof[j] < 30 or not 1540 <= j <= 1800:  # 오른쪽 물병은 화면 오른쪽에 있다(→ 약 1690–1760, ← 약 1580–1615)
            continue
        a, b = int(round(j - GAP - GAP_TOL)), int(round(j - GAP + GAP_TOL)) + 1
        if a < 5:
            continue
        i = a + int(np.argmax(prof[a:b]))
        key = (round(float(min(prof[i], 40.0)), 1), float(prof[j]))  # 왼쪽 자리에 물체가 있는 쪽, 그다음 오른쪽이 뚜렷한 쪽
        if best is None or key > best[0]:
            best = (key, i, j)
    if best is None:
        return None, peaks
    _, i, j = best
    flags = []
    if prof[i] > 5:
        xa = centre(i)
    else:
        xa = centre(j) - GAP
        flags.append("bottle_A_by_spacing")
    return ((xa, float(prof[i])), (centre(j), float(prof[j])), flags), peaks
