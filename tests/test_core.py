"""核心数据层测试。"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rijin.core.config import Config
from rijin.core.database import Database
from rijin.core.repository import Repository
from rijin.services.reminders import ReminderService


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.repo = Repository(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_create_sets_started_time_and_defaults(self):
        fixed = datetime(2026, 11, 15, 9, 30, 0)
        task = self.repo.create_task("写周报", project="工作", priority=2, at=fixed)
        self.assertEqual(task.started_at, fixed)
        self.assertEqual(task.created_at, fixed)
        self.assertEqual(task.status, "pending")
        self.assertIsNone(task.completed_at)
        self.assertEqual(task.priority, 2)

    def test_empty_detail_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.create_task("   ")

    def test_priority_sorting_today(self):
        now = datetime(2026, 11, 15, 10, 0, 0)
        due = datetime(2026, 11, 15, 18, 0, 0)
        self.repo.create_task("低", priority=0, due_at=due, at=now)
        self.repo.create_task("高", priority=2, due_at=due, at=now)
        self.repo.create_task("中", priority=1, due_at=due, at=now)
        tasks = self.repo.today_pending(now)
        self.assertEqual([t.detail for t in tasks], ["高", "中", "低"])

    def test_daily_prompt_included_every_day(self):
        now = datetime(2026, 11, 15, 10, 0, 0)
        self.repo.create_task("每日复盘", daily_prompt=True, at=now)
        self.assertEqual(len(self.repo.today_pending(now)), 1)
        later = datetime(2026, 11, 18, 10, 0, 0)
        self.assertEqual(len(self.repo.today_pending(later)), 1)

    def test_complete_and_reopen(self):
        now = datetime(2026, 11, 15, 10, 0, 0)
        task = self.repo.create_task("完成我", at=now)
        done = self.repo.complete_task(task.id, at=datetime(2026, 11, 15, 11, 0, 0))
        self.assertEqual(done.status, "done")
        self.assertEqual(done.completed_at, datetime(2026, 11, 15, 11, 0, 0))
        self.assertEqual(self.repo.stats_today(now)["completed"], 1)
        reopened = self.repo.reopen_task(task.id, at=datetime(2026, 11, 15, 11, 5, 0))
        self.assertEqual(reopened.status, "pending")
        self.assertIsNone(reopened.completed_at)
        self.assertEqual(reopened.started_at, now)

    def test_update_does_not_reset_started_at(self):
        now = datetime(2026, 11, 15, 10, 0, 0)
        task = self.repo.create_task("原", at=now)
        updated = self.repo.update_task(
            task.id,
            detail="新",
            priority=2,
            project="项目A",
            at=datetime(2026, 11, 15, 10, 5, 0),
        )
        self.assertEqual(updated.detail, "新")
        self.assertEqual(updated.started_at, now)
        self.assertEqual(updated.priority, 2)

    def test_claim_reminder_idempotent(self):
        now = datetime(2026, 11, 15, 10, 0, 0)
        task = self.repo.create_task("提醒", at=now)
        self.assertTrue(self.repo.claim_reminder(task.id, "remind", "x", now))
        self.assertFalse(self.repo.claim_reminder(task.id, "remind", "x", now))

    def test_claim_daily_state_advances(self):
        self.assertTrue(self.repo.claim_daily_state("last_digest_date", "2026-11-15"))
        self.assertFalse(self.repo.claim_daily_state("last_digest_date", "2026-11-15"))
        self.assertTrue(self.repo.claim_daily_state("last_digest_date", "2026-11-16"))


class ReminderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.repo = Repository(self.db)
        self.config_path = Path(self.tmp.name) / "config.json"
        self.config = Config(self.config_path)
        self.config.set("digest_time", "09:00")
        self.config.set("digest_enabled", True)
        self.service = ReminderService(self.repo, self.config)

    def tearDown(self):
        self.service.stop()
        self.db.close()
        self.tmp.cleanup()

    def test_digest_once_per_day(self):
        now = datetime(2026, 11, 15, 9, 1, 0)
        self.repo.create_task("今天要做", due_at=datetime(2026, 11, 15, 18, 0), at=now)
        events = self.service.tick(now)
        self.assertEqual([e["kind"] for e in events], ["digest"])
        self.assertEqual(events[0]["count"], 1)
        self.assertEqual(self.service.tick(datetime(2026, 11, 15, 9, 20, 0)), [])
        events2 = self.service.tick(datetime(2026, 11, 16, 9, 1, 0))
        self.assertEqual([e["kind"] for e in events2], ["due", "digest"])

    def test_digest_waits_until_configured_time(self):
        self.repo.create_task("今天要做", due_at=datetime(2026, 11, 15, 18, 0))
        self.assertEqual(self.service.tick(datetime(2026, 11, 15, 8, 59, 0)), [])
        self.assertEqual(len(self.service.tick(datetime(2026, 11, 15, 9, 0, 0))), 1)

    def test_task_reminder_once(self):
        now = datetime(2026, 11, 15, 10, 0, 0)
        self.repo.create_task(
            "开会",
            remind_at=datetime(2026, 11, 15, 10, 0),
            due_at=datetime(2026, 11, 15, 18, 0),
            at=datetime(2026, 11, 15, 8, 0),
        )
        self.config.set("digest_time", "23:59")
        events = self.service.tick(now)
        self.assertEqual([e["kind"] for e in events], ["remind"])
        self.assertEqual(self.service.tick(datetime(2026, 11, 15, 10, 1, 0)), [])

    def test_due_event_at_last_prompt_time(self):
        self.config.set("digest_time", "23:59")
        self.repo.create_task(
            "交报告",
            due_at=datetime(2026, 11, 15, 17, 0),
            at=datetime(2026, 11, 15, 8, 0),
        )
        events = self.service.tick(datetime(2026, 11, 15, 17, 0, 30))
        self.assertEqual([e["kind"] for e in events], ["due"])
        self.assertIn("最后提醒", events[0]["body"])
        self.assertEqual(self.service.tick(datetime(2026, 11, 15, 17, 1, 0)), [])

    def test_daily_prompt_notifies_each_day(self):
        self.config.set("digest_time", "23:59")
        self.repo.create_task(
            "每日拉伸",
            remind_at=datetime(2026, 11, 15, 20, 0),
            daily_prompt=True,
            at=datetime(2026, 11, 15, 8, 0),
        )
        first = self.service.tick(datetime(2026, 11, 15, 20, 1))
        self.assertEqual([e["kind"] for e in first], ["remind"])
        second = self.service.tick(datetime(2026, 11, 16, 20, 1))
        self.assertEqual([e["kind"] for e in second], ["remind"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
