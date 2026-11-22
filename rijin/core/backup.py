"""数据导出与备份。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .database import Database
from .paths import backup_dir
from .repository import Repository


def export_json(repository: Repository, target: Path, config: Dict[str, Any] = None) -> Path:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "app": "日进",
        "version": 1,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tasks": repository.export_snapshot(),
        "config": config or {},
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def daily_backup(database: Database, keep: int = 14) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    target = backup_dir() / ("rijin-%s.db" % stamp)
    if not target.exists():
        database.backup_to(target)
    backups = sorted(backup_dir().glob("rijin-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass
    return target
