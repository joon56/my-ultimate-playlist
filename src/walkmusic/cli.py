"""명령줄: ``python -m walkmusic inspect|qa|process|stats|all``.

process·stats·all은 실험 1이다. 실제 데이터는 분석 고정 태그가 있어야 돈다(D-35). figures·freeze는 아직 없다.
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
    p_qa.add_argument("--links", action="store_true",
                      help="data/raw/<사람>/의 zip을 기록지 시각과 맞춘 연결 제안(results/zip_links.csv)만 낸다")

    for name, text in (("process", "실험 1: 곡 구간·회차·사람 표(segments·walks·participants.csv)"),
                       ("stats", "실험 1: 가설 판정·처방 범위·시나리오 신호(hypotheses·prescription·g2_flags.csv)"),
                       ("all", "process 다음 stats")):
        sp = sub.add_parser(name, help=text)
        sp.add_argument("--synthetic", action="store_true", help="합성 자료로(results_synthetic/exp1/에만 쓴다)")
        sp.add_argument("--allow-unfrozen", action="store_true",
                        help="분석 고정 태그 없이 실제 데이터로 돌린다(run_info.json에 unfrozen=true, D-35)")
    return ap


def _run_exp1(command: str, synthetic: bool, allow_unfrozen: bool) -> int:
    from walkmusic.config import ROOT, load_params
    from walkmusic.exp1 import make_synthetic_dataset, synthetic_paths
    from walkmusic.qa import Paths
    from walkmusic.stats import FreezeError, run_pipeline

    params = load_params()
    if synthetic:
        root = ROOT / "results_synthetic" / "exp1"
        paths = synthetic_paths(root)
        if not paths.manifest.exists():
            print("합성 실험 1 자료를 만든다(처음 한 번, 1–2분)")
            make_synthetic_dataset(root, params)
    else:
        paths = Paths.real()
    try:
        summary = run_pipeline(paths, params, real=not synthetic, allow_unfrozen=allow_unfrozen,
                               do_process=command in ("process", "all"), do_stats=command in ("stats", "all"))
    except FreezeError as e:
        print(e)
        return 3
    print(f"결과 → {paths.results}")
    for r in summary.get("hypotheses", []):
        if r["participant"] == "ALL":
            print(f"{r['hypothesis']}: 집단 {r['supported']} ({r['note']})")
    return 0


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
                       synthetic=args.synthetic, links=args.links)
    if args.command in ("process", "stats", "all"):
        return _run_exp1(args.command, args.synthetic, args.allow_unfrozen)
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
