"""本地时间与中文展示工具。统一使用本地朴素时间，避免跨时区歧义。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

WEEKDAYS_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def now_local() -> datetime:
    return datetime.now().replace(microsecond=0)


def to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None


def date_key(value: Optional[datetime] = None) -> str:
    return (value or now_local()).strftime("%Y-%m-%d")


def start_of_day(value: Optional[datetime] = None) -> datetime:
    current = value or now_local()
    return datetime.combine(current.date(), time.min)


def day_bounds(value: Optional[datetime] = None):
    current = value or now_local()
    start = datetime.combine(current.date(), time.min)
    return start, start + timedelta(days=1)


def human_date(value: Optional[datetime] = None) -> str:
    current = value or now_local()
    return "%d月%d日 · %s" % (current.month, current.day, WEEKDAYS_CN[current.weekday()])


def human_date_full(value: Optional[datetime] = None) -> str:
    current = value or now_local()
    return "%d年%d月%d日 %s" % (current.year, current.month, current.day, WEEKDAYS_CN[current.weekday()])


def human_due(value: Optional[datetime], now: Optional[datetime] = None) -> str:
    """把截止时间转成今天 18:00 / 明天 09:30 / 11月20日 18:00。"""
    if value is None:
        return "未设截止"
    current = now or now_local()
    delta_days = (value.date() - current.date()).days
    clock = value.strftime("%H:%M")
    if delta_days == 0:
        return "今天 " + clock
    if delta_days == 1:
        return "明天 " + clock
    if delta_days == -1:
        return "昨天 " + clock
    if value.year == current.year:
        return "%d月%d日 %s" % (value.month, value.day, clock)
    return "%d年%d月%d日 %s" % (value.year, value.month, value.day, clock)


def human_short(value: Optional[datetime], now: Optional[datetime] = None) -> str:
    if value is None:
        return "—"
    current = now or now_local()
    if value.date() == current.date():
        return value.strftime("%H:%M")
    if value.year == current.year:
        return "%d/%d %s" % (value.month, value.day, value.strftime("%H:%M"))
    return "%d/%d/%d %s" % (value.year, value.month, value.day, value.strftime("%H:%M"))


def human_completed(value: Optional[datetime]) -> str:
    if value is None:
        return "已完成"
    return value.strftime("%H:%M") + " 完成"


def seconds_until(target: datetime, now: Optional[datetime] = None) -> float:
    current = now or now_local()
    return (target - current).total_seconds()


def combine_date_time(day: date, clock: str) -> datetime:
    hour, minute = [int(x) for x in clock.split(":")]
    return datetime.combine(day, time(hour=hour, minute=minute))


def next_half_hour(value: Optional[datetime] = None) -> datetime:
    current = (value or now_local()).replace(second=0, microsecond=0)
    remainder = current.minute % 30
    if remainder:
        current += timedelta(minutes=30 - remainder)
    else:
        current += timedelta(minutes=30)
    return current
