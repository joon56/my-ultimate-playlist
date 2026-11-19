"""명령줄 옵션 (SPEC §10)."""

from walkmusic.cli import _build_parser


def test_exp23_command_options():
    a = _build_parser().parse_args(["exp23", "--links", "--date", "2026-11-21"])
    assert (a.command, a.links, a.date, a.synthetic, a.allow_unfrozen) == ("exp23", True, "2026-11-21", False, False)
