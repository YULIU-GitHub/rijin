"""控制器端到端测试：通过真实对话框完成增改、完成与撤销。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from rijin.app_controller import AppController  # noqa: E402
from rijin.core.config import Config  # noqa: E402
from rijin.core.database import Database  # noqa: E402
from rijin.core.repository import Repository  # noqa: E402
from rijin.ui import theme  # noqa: E402
from rijin.ui.dialogs import TaskDialog  # noqa: E402


class ControllerFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(theme.stylesheet(ROOT / "assets"))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_data_dir = os.environ.get("RIJIN_DATA_DIR")
        os.environ["RIJIN_DATA_DIR"] = self.tmp.name
        self.db = Database(Path(self.tmp.name) / "flow.db")
        self.repo = Repository(self.db)
        self.config = Config(Path(self.tmp.name) / "config.json")
        self.controller = AppController(self.app, self.config, self.db, self.repo)

    def tearDown(self):
        self.controller.shutdown()
        self.tmp.cleanup()
        if self._old_data_dir is None:
            os.environ.pop("RIJIN_DATA_DIR", None)
        else:
            os.environ["RIJIN_DATA_DIR"] = self._old_data_dir

    def _fill_dialog(self, detail, project="测试项目", priority=2):
        for widget in self.app.topLevelWidgets():
            if isinstance(widget, TaskDialog) and widget.isVisible():
                widget.detail_edit.setPlainText(detail)
                widget.project_combo.setCurrentText(project)
                widget._set_priority(priority)
                widget.note_edit.setText("由自动化测试创建")
                widget._save()
                return
        QTimer.singleShot(60, lambda: self._fill_dialog(detail, project, priority))

    def test_add_edit_complete_reopen(self):
        QTimer.singleShot(80, lambda: self._fill_dialog("自动测试：写一份测试计划"))
        self.controller.open_add()
        pending = self.controller.store.list_tasks(view="pending")
        self.assertEqual(len(pending), 1)
        task = pending[0]
        self.assertEqual(task.project, "测试项目")
        self.assertEqual(task.priority, 2)
        self.assertIsNotNone(task.started_at)

        QTimer.singleShot(80, lambda: self._fill_dialog("自动测试：修改后的明细", "测试项目", 1))
        self.controller.edit_task(task.id, "float")
        updated = self.controller.store.get(task.id)
        self.assertEqual(updated.detail, "自动测试：修改后的明细")
        self.assertEqual(updated.priority, 1)

        self.controller.complete_task(task.id, "float")
        done = self.controller.store.get(task.id)
        self.assertTrue(done.is_done)
        self.assertIsNotNone(done.completed_at)

        self.controller.reopen_task(task.id, "float")
        again = self.controller.store.get(task.id)
        self.assertFalse(again.is_done)
        self.assertIsNone(again.completed_at)

    def test_toast_action_invokes_callback(self):
        called = []
        self.controller.float_window.show_toast("已完成「测试」", "撤销", lambda: called.append(True))
        self.app.processEvents()
        self.assertFalse(self.controller.float_window.toast.action.isHidden())
        self.assertEqual(self.controller.float_window.toast.action.text(), "撤销")
        self.controller.float_window.toast.action.click()
        self.assertEqual(called, [True])


if __name__ == "__main__":
    unittest.main(verbosity=2)
