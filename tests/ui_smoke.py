"""开发用 UI 冒烟测试：构造全部窗口，不进入事件循环。

用法：
    set QT_QPA_PLATFORM=offscreen
    python tests/ui_smoke.py
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

tmp = tempfile.TemporaryDirectory()
os.environ["RIJIN_DATA_DIR"] = tmp.name

from PyQt5.QtWidgets import QApplication  # noqa: E402

from rijin.core.config import Config  # noqa: E402
from rijin.core.database import Database  # noqa: E402
from rijin.core.paths import assets_dir  # noqa: E402
from rijin.core.repository import Repository  # noqa: E402
from rijin.services.store import TaskStore  # noqa: E402
from rijin.ui import theme  # noqa: E402
from rijin.ui.dialogs import SettingsDialog, TaskDialog  # noqa: E402
from rijin.ui.main_window import FloatWindow  # noqa: E402
from rijin.ui.task_center import TaskCenter  # noqa: E402


def main() -> int:
    app = QApplication([])
    app.setStyleSheet(theme.stylesheet(assets_dir()))
    base = Path(tmp.name)
    db = Database(base / "ui.db")
    repo = Repository(db)
    now = datetime.now().replace(microsecond=0)
    first = repo.create_task(
        "完成第三季度复盘初稿，整理关键指标与结论",
        project="工作",
        priority=2,
        remind_at=now + timedelta(hours=1),
        due_at=now + timedelta(hours=3),
        daily_prompt=True,
        note="先拉数据，再写结论",
    )
    repo.create_task(
        "阅读《原则》第二章并做笔记",
        project="学习",
        priority=1,
        remind_at=now + timedelta(hours=2),
        due_at=now + timedelta(hours=4),
    )
    repo.create_task(
        "整理本周账单与报销单",
        project="生活",
        priority=0,
        remind_at=now + timedelta(hours=1),
        due_at=now + timedelta(hours=2),
    )
    done = repo.create_task("已完成的任务示例", project="工作", priority=1)
    repo.complete_task(done.id, at=now)

    store = TaskStore(repo)
    config = Config(base / "config.json")

    window = FloatWindow(store, config)
    window.show()
    app.processEvents()
    print("float rows", len(window._rows), window.size())
    window.set_expanded(True, animate=False)
    app.processEvents()
    print("float expanded", window.size())

    center = TaskCenter(store, config)
    center.show_center("today")
    app.processEvents()
    print("center", center.size(), "rows", len(center._rows))
    for view in ("completed", "daily", "pending", "today"):
        center.set_view(view)
        app.processEvents()
        print(view, len(center._rows))

    dialog = TaskDialog(center, repo, first)
    dialog.show()
    app.processEvents()
    print("task dialog", dialog.size())
    dialog.close()

    settings = SettingsDialog(center, config, repo)
    settings.show()
    app.processEvents()
    print("settings", settings.size())
    settings.close()

    print("UI SMOKE OK")
    window.close()
    center.set_quitting()
    center.close()
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
