"""진자 영상에서 테이프 마커(빨강 = 대전자, 파랑 = 무릎 아래, 노랑 = 복사뼈 위)의 중심을 프레임마다 찾는다. 화소만 읽는다.

사용(저장소 맨 위에서): python -I tools/video/marker_track.py <영상> <출력 폴더> [--sheet T0 T1]
출력: <stem>_cands.npz(후보), <stem>_markers.npz(t, yellow, blue, red: 원본 화소 좌표, 못 찾으면 nan), --sheet면 확인 그림.

방법
1. 반 해상도로 읽는다. 색 조건: 노랑 R > 170, G > 160, R − B > 55, |R − G| < 45 · 파랑 B − R > 70, B > 140, B − G > 40 ·
   빨강 R − G > 70, R − B > 50, R > 140.
2. 프레임마다 색 덩어리 후보를 모두 적어 둔다(<stem>_cands.npz). 가만히 있는 덩어리(배경의 파란 칸, 구석의 노란 물건: 20프레임
   앞뒤 모두에 25 px 안의 덩어리가 있는 것)는 뺀다.
3. 노랑 = 남은 것 중 앞 프레임에서 가장 가까운 덩어리(pick_yellow). 파랑 = 노랑과의 거리가 영상 내내 거의 같은 것(pick_blue).
   빨강 = 가장 큰 덩어리.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vframes as fr  # noqa: E402

S = 0.5  # 읽는 해상도 비율


def masks(a: np.ndarray) -> dict[str, np.ndarray]:
    R, G, B = a[..., 0].astype(np.int16), a[..., 1].astype(np.int16), a[..., 2].astype(np.int16)
    return dict(yellow=(R > 170) & (G > 160) & (R - B > 55) & (np.abs(R - G) < 45),
                blue=(B - R > 70) & (B > 140) & (B - G > 40),
                red=(R - G > 70) & (R - B > 50) & (R > 140))


def blobs(m: np.ndarray, min_area: int) -> list[tuple[float, float, float]]:
    lab, n = ndi.label(m)
    if not n:
        return []
    idx = np.arange(1, n + 1)
    area = ndi.sum(m, lab, idx)
    keep = idx[area >= min_area]
    if not len(keep):
        return []
    com = ndi.center_of_mass(m, lab, keep)
    return [(float(c[1]), float(c[0]), float(area[k - 1])) for c, k in zip(com, keep)]


def pick_blue(cands: dict, Y: np.ndarray):
    """프레임별 파란 덩어리 후보(x, y, 넓이, 노랑과의 거리)에서 테이프를 고른다.

    (1) 가만히 있는 덩어리(_moving)는 배경이라 뺀다. (2) 테이프는 노랑과의 거리가 거의 같다:
    남은 후보 거리의 최빈값 d0의 0.80–1.12배(다리가 화면 밖으로 돌면 조금 짧아 보인다), 넓이 1500–9000 px.
    (3) 그런 후보가 하나뿐이고 넓이가 보통인 프레임을 씨앗으로, 노랑에서 본 방향이 조금씩만 바뀌도록 앞뒤로 이어 간다.
    """
    n = len(Y)
    B, AB = np.full((n, 2), np.nan), np.full(n, np.nan)
    moving = _moving(cands)
    alld = np.array([c[3] for v in moving.values() for c in v if 120 <= c[3] <= 520 and 1500 <= c[2] <= 9000])
    if len(alld) <= 50:
        return B, AB, None
    hist, edges = np.histogram(alld, bins=np.arange(120, 524, 4))
    k = int(np.argmax(np.convolve(hist, np.ones(5), mode="same")))
    d0 = float(np.median(alld[(alld >= edges[k] - 12) & (alld <= edges[k + 1] + 12)]))
    ok = {i: [c for c in v if 0.80 * d0 <= c[3] <= 1.12 * d0 and 1500 <= c[2] <= 9000] for i, v in moving.items()}
    single = [v[0][2] for v in ok.values() if len(v) == 1]
    if not single:
        return B, AB, d0
    a0 = float(np.median(single))  # 후보가 하나뿐인 프레임의 넓이
    seeds = {i for i, v in ok.items() if len(v) == 1 and abs(v[0][2] - a0) < 0.3 * a0 and abs(v[0][3] - d0) < 0.06 * d0}
    for direction in (1, -1):  # 씨앗에서 앞뒤로 이어 간다
        last = {}
        for i in (sorted(ok) if direction == 1 else sorted(ok, reverse=True)):
            if np.isfinite(B[i, 0]):
                last = dict(i=i, r=B[i] - Y[i])
                continue
            v = ok[i]
            if i in seeds:
                c = v[0]
            elif v and last and abs(i - last["i"]) <= 6:
                c = min(v, key=lambda c: np.hypot(c[0] - Y[i, 0] - last["r"][0], c[1] - Y[i, 1] - last["r"][1]))
                if np.hypot(c[0] - Y[i, 0] - last["r"][0], c[1] - Y[i, 1] - last["r"][1]) > 12 * abs(i - last["i"]) + 20:
                    continue
            else:
                continue
            B[i], AB[i] = (c[0], c[1]), c[2]
            last = dict(i=i, r=B[i] - Y[i])
    return B, AB, d0


def _moving(cands: dict, lag: int = 20, tol: float = 25.0) -> dict:
    """가만히 있는 덩어리(배경)를 뺀다: 20프레임 앞과 뒤 모두에 25 px 안의 덩어리가 있으면 가만히 있는 것이다.

    흔들리는 다리의 테이프는 1/3 s 앞뒤 가운데 적어도 한쪽에서는 자리를 옮긴다(주기 1.2–1.6 s). 손으로 든 카메라가 천천히 움직여도
    배경은 1/3 s 사이에 거의 그대로다. 서 있는 동안의 테이프도 빠진다(그 구간은 쓰지 않는다).
    """
    out = {}
    for i, v in cands.items():
        keep = []
        for c in v:
            hits = [any(abs(c[0] - o[0]) <= tol and abs(c[1] - o[1]) <= tol for o in cands[j]) for j in (i - lag, i + lag) if j in cands]
            if not (hits and all(hits)):
                keep.append(c)
        out[i] = keep
    return out


def pick_yellow(cands: dict, n: int):
    """프레임별 노란 덩어리 후보(x, y, 넓이)에서 발목 테이프를 고른다: 배경(가만히 있는 것)을 빼고, 앞 프레임에서 가장 가까운
    덩어리(60 px 넘게 뛰면 가장 큰 덩어리로 다시 잡는다)."""
    Y, AY = np.full((n, 2), np.nan), np.full(n, np.nan)
    prev = None
    for i, v in sorted(_moving(cands).items()):
        if not v:
            continue
        c = min(v, key=lambda b: (b[0] - prev[0]) ** 2 + (b[1] - prev[1]) ** 2) if prev is not None else max(v, key=lambda b: b[2])
        if prev is not None and np.hypot(c[0] - prev[0], c[1] - prev[1]) > 60:
            c = max(v, key=lambda b: b[2])
        Y[i], AY[i], prev = (c[0], c[1]), c[2], c
    return Y, AY


def track(video: Path, out: Path) -> dict:
    pts = fr.pts_table(video, out)
    n = len(pts)
    H, AH = np.full((n, 2), np.nan), np.full(n, np.nan)
    yc, bc = {}, {}
    for i, _, a in fr.frames(video, 0.0, float(pts[-1]), None, S, pts):
        m = masks(a)
        yc[i] = [(b[0] / S, b[1] / S, b[2] / S ** 2) for b in blobs(m["yellow"], 60)]
        bc[i] = [(b[0] / S, b[1] / S, b[2] / S ** 2) for b in blobs(m["blue"], 120)]
        rb = blobs(m["red"], 100)
        if rb:
            c = max(rb, key=lambda b: b[2])
            H[i], AH[i] = (c[0] / S, c[1] / S), c[2] / S ** 2
    flat = lambda d: np.array([(i, *c) for i, v in d.items() for c in v], dtype=float).reshape(-1, 4)
    np.savez(out / f"{video.stem}_cands.npz", t=pts, yellow=flat(yc), blue=flat(bc), red=H, area_red=AH)
    return pick(out, video.stem)


def pick(out: Path, stem: str) -> dict:
    """후보 파일(<stem>_cands.npz)에서 노랑·파랑을 골라 <stem>_markers.npz를 쓴다(영상을 다시 읽지 않는다)."""
    z = np.load(out / f"{stem}_cands.npz")
    pts, n = z["t"], len(z["t"])
    group = lambda arr: {int(i): [tuple(r[1:]) for r in arr[arr[:, 0] == i]] for i in np.unique(arr[:, 0])}
    Y, AY = pick_yellow(group(z["yellow"]), n)
    cands = {i: [(c[0], c[1], c[2], float(np.hypot(c[0] - Y[i, 0], c[1] - Y[i, 1]))) for c in v]
             for i, v in group(z["blue"]).items() if np.isfinite(Y[i, 0])}
    B, AB, d0 = pick_blue(cands, Y)
    np.savez(out / f"{stem}_markers.npz", t=pts, yellow=Y, blue=B, red=z["red"], area_yellow=AY, area_blue=AB, area_red=z["area_red"],
             d0=np.nan if d0 is None else d0)
    return dict(t=pts, yellow=Y, blue=B, red=z["red"], d0=d0)


def check_sheet(video: Path, out: Path, r: dict, t0: float, t1: float, n: int = 12):
    pts = r["t"]
    idx = np.linspace(np.searchsorted(pts, t0), np.searchsorted(pts, t1) - 1, n).astype(int)
    tiles = []
    for i in idx:
        _, t, a = fr.read(video, pts[i], pts[i], None, S, pts)[0]
        im = Image.fromarray(a)
        d = ImageDraw.Draw(im)
        for key, col in (("yellow", (255, 0, 255)), ("blue", (0, 255, 0)), ("red", (0, 255, 255))):
            x, y = r[key][i] * S
            if np.isfinite(x):
                d.ellipse([x - 5, y - 5, x + 5, y + 5], outline=col, width=2)
                d.line([x - 12, y, x + 12, y], fill=col)
                d.line([x, y - 12, x, y + 12], fill=col)
        d.text((4, 2), f"{i} {t:.2f}s", fill=(255, 255, 0))
        tiles.append(im)
    w, h = tiles[0].size
    cols = 4 if w > h else 6
    sh = Image.new("RGB", (cols * w, ((len(tiles) + cols - 1) // cols) * h))
    for k, im in enumerate(tiles):
        sh.paste(im, ((k % cols) * w, (k // cols) * h))
    f = 2400 / sh.width
    sh.resize((2400, int(sh.height * f))).save(out / f"{video.stem}_markers.jpg", quality=88)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--sheet", nargs=2, type=float, metavar=("T0", "T1"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    r = track(a.video, a.out)
    ok = {k: int(np.isfinite(r[k][:, 0]).sum()) for k in ("yellow", "blue", "red")}
    print(f"{a.video.name}: 프레임 {len(r['t'])}, 찾은 프레임 노랑 {ok['yellow']} 파랑 {ok['blue']} 빨강 {ok['red']}, 노랑–파랑 거리 {r['d0'] and round(r['d0'], 1)} px")
    if a.sheet:
        check_sheet(a.video, a.out, r, a.sheet[0], a.sheet[1])
