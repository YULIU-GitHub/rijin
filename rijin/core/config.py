"""轻量配置。JSON 存储，便于查看、备份和后续增加字段。"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Any] = {
    "version": 1,
    "digest_enabled": True,
    "digest_time": "09:00",
    "notifications_enabled": True,
    "auto_expand": True,
    "hover_expand": True,
    "always_on_top": True,
    "close_to_tray": True,
    "floating_pos": None,
    "floating_pinned": False,
    "last_version": "1.0.0",
}

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def valid_time(value: str) -> str:
    match = _TIME_RE.match(str(value or "").strip())
    if not match:
        return DEFAULTS["digest_time"]
    return "%02d:%02d" % (int(match.group(1)), int(match.group(2)))


class Config:
    """点对式配置对象。

    写入采用临时文件替换，避免程序被强制关闭时损坏配置。
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key, value in raw.items():
                    self.data[key] = value
        except (OSError, ValueError):
            # 配置损坏时保留默认值；原文件由调用方按需备份。
            pass
        self.data["digest_time"] = valid_time(self.get("digest_time", DEFAULTS["digest_time"]))

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        if key in self.data:
            return self.data[key]
        if default is not None:
            return default
        return DEFAULTS.get(key)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def update(self, values: Dict[str, Any]) -> None:
        self.data.update(values)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".json.tmp")
        payload = json.dumps(self.data, ensure_ascii=False, indent=2)
        temp.write_text(payload, encoding="utf-8")
        temp.replace(self.path)

    def as_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.data)
