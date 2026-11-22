"""데이터 동결 (SPEC §7 `frozen/v1.0/`, §12 Phase 4): 결과 CSV를 판 번호 폴더에 복사하고 SHA256SUMS를 쓴다.

분석 고정(git 태그 `analysis-freeze-g2`, D-35)과는 다른 것이다. 같은 판 번호가 이미 있으면 덮어쓰지 않고 멈춘다.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from walkmusic.stats import _sha


def frozen_files(results: Path) -> list[Path]:
    """동결할 파일: results 아래 모든 CSV(동결 폴더 제외)와 맨 위의 run_info*.json. 상대 경로 순서."""
    results = Path(results)
    files = [p for p in results.rglob("*.csv") if "frozen" not in p.relative_to(results).parts]
    return sorted(files + list(results.glob("run_info*.json")), key=lambda p: p.relative_to(results).as_posix())


def freeze_results(results: Path, version: str) -> Path:
    """results의 결과 표를 results/frozen/v<version>/에 복사하고 SHA256SUMS(sha256  상대 경로)를 쓴다.

    그 판이 이미 있으면 FileExistsError, 동결할 파일이 없으면 FileNotFoundError.
    """
    if not re.fullmatch(r"\d+(\.\d+)*", version):
        raise ValueError(f"판 번호는 1.0처럼 숫자와 점으로 적는다: '{version}'")
    results = Path(results)
    target = results / "frozen" / f"v{version}"
    if target.exists():
        raise FileExistsError(f"{target}이 이미 있다. 동결본은 덮어쓰지 않는다(다른 판 번호를 쓴다)")
    files = frozen_files(results)
    if not files:
        raise FileNotFoundError(f"{results}에 동결할 결과 표가 없다")
    lines = []
    for src in files:
        rel = src.relative_to(results)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        lines.append(f"{_sha(dst)}  {rel.as_posix()}")
    (target / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return target
