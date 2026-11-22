"""应用路径。数据与代码分离，升级程序不会影响任务数据。"""
from __future__ import annotations

import os
from pathlib import Path

APP_SLUG = "RiJin"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def assets_dir() -> Path:
    return project_root() / "assets"


def data_dir() -> Path:
    override = os.environ.get("RIJIN_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / APP_SLUG


def config_path() -> Path:
    return data_dir() / "config.json"


def database_path() -> Path:
    return data_dir() / "rijin.db"


def log_dir() -> Path:
    return data_dir() / "logs"


def backup_dir() -> Path:
    return data_dir() / "backups"


def ensure_data_dirs() -> None:
    for path in (data_dir(), log_dir(), backup_dir()):
        path.mkdir(parents=True, exist_ok=True)
