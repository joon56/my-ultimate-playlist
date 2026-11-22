"""영상의 프레임 일부를 잘라 번호(프레임 번호 n, 시각)와 함께 한 장에 늘어놓는다. 화소만 읽는다.

사용: python -I tools/video/vframes.py <영상> <출력 jpg> --t0 11.4 --t1 12.7 [--step 3] [--crop x y w h] [--scale 0.5] [--cols 12]
프레임 번호 n은 표시 순서(0부터), 시각은 컨테이너의 pts(s)다.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def pts_table(video: Path, cache: Path) -> np.ndarray:
    f = cache / (video.stem + "_pts.json")
    if f.exists():
        return np.array(json.loads(f.read_text()))
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-of", "csv=p=0",
                          str(video)], capture_output=True, text=True, check=True).stdout
    p = np.sort(np.array([float(x.strip().strip(",")) for x in out.split() if x.strip().strip(",")]))
    f.write_text(json.dumps(p.tolist()))
    return p


def size(video: Path) -> tuple[int, int]:
    """표시 방향(회전 반영)의 프레임 크기."""
    import io
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(out)).size


def frames(video: Path, t0: float, t1: float, crop, scale: float, pts: np.ndarray, step: int = 1):
    """[t0, t1] 안 프레임을 (n, pts, RGB 배열)로 하나씩 낸다(긴 영상은 이것으로 읽는다: 한꺼번에 쌓지 않는다)."""
    W, H = size(video)
    x, y, w, h = crop if crop else (0, 0, W, H)
    x, y, w, h = (int(v) // 2 * 2 for v in (x, y, w, h))
    ow, oh = int(round(w * scale)) // 2 * 2, int(round(h * scale)) // 2 * 2
    idx = np.flatnonzero((pts >= t0 - 1e-6) & (pts <= t1 + 1e-6))
    ss = max(t0 - 1.5, 0.0)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-copyts", "-i", str(video), "-vf",
           f"select='between(t,{t0 - 1e-4:.5f},{t1 + 1e-4:.5f})',crop={w}:{h}:{x}:{y},scale={ow}:{oh}", "-vsync", "0", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    k, nb = 0, ow * oh * 3
    while True:
        buf = p.stdout.read(nb)
        if len(buf) < nb:
            break
        if k < len(idx) and (k % step == 0):
            yield int(idx[k]), float(pts[idx[k]]), np.frombuffer(buf, np.uint8).reshape(oh, ow, 3).copy()
        k += 1
    p.stdout.close()
    p.wait()
    if k != len(idx):
        print(f"경고: 읽은 프레임 {k}개, 시각표 {len(idx)}개", file=sys.stderr)


def read(video: Path, t0: float, t1: float, crop, scale: float, pts: np.ndarray, step: int = 1) -> list:
    """frames()를 목록으로(짧은 구간에만 쓴다)."""
    return list(frames(video, t0, t1, crop, scale, pts, step))


def sheet(frames, cols: int, out: Path, label=True):
    if not frames:
        raise SystemExit("프레임이 없다")
    h, w = frames[0][2].shape[:2]
    rows = (len(frames) + cols - 1) // cols
    im = Image.new("RGB", (cols * w, rows * (h + 14)), (0, 0, 0))
    dr = ImageDraw.Draw(im)
    for i, (n, t, a) in enumerate(frames):
        cx, cy = (i % cols) * w, (i // cols) * (h + 14)
        im.paste(Image.fromarray(a), (cx, cy + 14))
        if label:
            dr.text((cx + 2, cy + 1), f"{n}  {t:.3f}", fill=(255, 255, 0))
    im.save(out, quality=90)
    print(f"{out.name}: {len(frames)}장, 칸 {w}x{h}, 프레임 {frames[0][0]}–{frames[-1][0]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--crop", type=int, nargs=4)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--cols", type=int, default=10)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    pts = pts_table(a.video, a.out.parent)
    sheet(read(a.video, a.t0, a.t1, a.crop, a.scale, pts, a.step), a.cols, a.out)
