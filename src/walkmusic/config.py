"""config/params.toml 읽기.

키는 문서(SPEC, QA_CHECKLIST, DECISIONS)와 같은 '섹션.키' 이름으로 꺼낸다.
예: ``params["qa.gap_warn_s"]``. 없는 키는 KeyError를 낸다(기본값을 숨기지 않는다).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - DECISIONS D-40
    import tomli as tomllib

#: 저장소 루트(src 배치: src/walkmusic/config.py → 두 단계 위)
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "config" / "params.toml"


class Params:
    """params.toml 내용. ``params["섹션.키"]``로 값을 꺼낸다."""

    def __init__(self, data: Mapping[str, Any], path: Path | None = None) -> None:
        self._data = data
        self.path = path

    def __getitem__(self, dotted: str) -> Any:
        section, _, key = dotted.partition(".")
        if not key or section not in self._data or key not in self._data[section]:
            raise KeyError(f"params.toml에 '{dotted}'가 없다")
        return self._data[section][key]

    def __contains__(self, dotted: str) -> bool:
        try:
            self[dotted]
        except KeyError:
            return False
        return True

    def sections(self) -> list[str]:
        """섹션 이름 목록."""
        return list(self._data)

    def keys(self) -> list[str]:
        """'섹션.키' 전체 목록."""
        return [f"{s}.{k}" for s, sec in self._data.items() for k in sec]


def load_params(path: str | Path | None = None) -> Params:
    """params.toml을 읽어 :class:`Params`로 돌려준다. path가 없으면 저장소의 config/params.toml."""
    p = Path(path) if path else DEFAULT_PATH
    with open(p, "rb") as f:
        return Params(tomllib.load(f), p)
