"""명령줄: ``python -m walkmusic inspect|qa``.

Phase 1 명령만 있다(process, stats, figures, freeze, all은 Phase 2 이후).
좌표 값과 기기 이름은 어떤 출력에도 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m walkmusic", description="walk-music 분석 (Phase 1: inspect, qa)")
    sub = ap.add_subparsers(dest="command", required=True)

    p_in = sub.add_parser("inspect", help="zip의 파일 구조와 시간·샘플링 요약(좌표 출력 없음)")
    p_in.add_argument("zip", type=Path, help="Sensor Logger zip 경로")

    p_qa = sub.add_parser("qa", help="품질 검사 Q01-Q15")
    p_qa.add_argument("zip", type=Path, nargs="?", help="검사할 zip 하나(manifest의 zip_file 또는 walk_id로 찾는다)")
    p_qa.add_argument("--walk", help="walk_id로 한 회차만")
    p_qa.add_argument("--all", action="store_true", help="manifest의 모든 회차")
    p_qa.add_argument("--gate", choices=["G1"], help="관문 표를 만든다(모든 회차 QA 뒤)")
    p_qa.add_argument("--synthetic", action="store_true", help="합성 데이터로(results_synthetic/에만 쓴다)")
    return ap


def main(argv: list[str] | None = None) -> int:
    """명령을 실행하고 종료 코드를 돌려준다."""
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔(cp949)에서 못 찍는 기호는 ?로 바꾼다
        try:
            stream.reconfigure(errors="replace")
        except AttributeError:  # pragma: no cover
            pass
    args = _build_parser().parse_args(argv)
    if args.command == "inspect":
        from walkmusic.io_sensorlogger import inspect_report, read_zip

        print(inspect_report(read_zip(args.zip)))
        return 0
    if args.command == "qa":
        from walkmusic.qa import run_cli

        return run_cli(zip_path=args.zip, walk=args.walk, all_walks=args.all, gate=args.gate,
                       synthetic=args.synthetic)
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
