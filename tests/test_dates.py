# -*- coding: utf-8 -*-
import unittest
from datetime import datetime

from xian_activities.dates import parse_date_range, parse_month_day_range, parse_timestamp


class DateRangeTest(unittest.TestCase):
    def test_exhibition_range(self):
        start, end = parse_date_range("2026年7月6日至10月11日")
        self.assertTrue(start.startswith("2026-07-06"))
        self.assertTrue(end.startswith("2026-10-11"))

    def test_range_with_time(self):
        start, end = parse_date_range("11月07日 周六 19:30 ~ 11月29日 周日 19:35")
        self.assertIn("T19:30", start)
        self.assertIn("T19:35", end)
        self.assertEqual(start[:7], end[:7])

    def test_single_date(self):
        start, end = parse_date_range("2026-11-03")
        self.assertTrue(start.startswith("2026-11-03"))
        self.assertIsNone(end)

    def test_cross_year(self):
        start, end = parse_date_range("2026年12月28日至1月3日")
        self.assertTrue(start.startswith("2026-12-28"))
        self.assertTrue(end.startswith("2027-01-03"))

    def test_garbage(self):
        self.assertEqual(parse_date_range("详情见页面"), (None, None))


class MonthDayTest(unittest.TestCase):
    def test_hdx_range(self):
        start, end = parse_month_day_range("11/21 周六 ~ 11/22 周日")
        self.assertIsNotNone(start)
        self.assertGreaterEqual(start[:7], str(datetime.now().year))

    def test_single(self):
        start, _ = parse_month_day_range("12/27 周日 19:30")
        self.assertIn("T00:00", start)


class TimestampTest(unittest.TestCase):
    def test_valid(self):
        iso = parse_timestamp(1738166400)
        self.assertTrue(iso.startswith("2025-01-30"))

    def test_invalid(self):
        self.assertIsNone(parse_timestamp(0))
        self.assertIsNone(parse_timestamp("abc"))


if __name__ == "__main__":
    unittest.main()
