# -*- coding: utf-8 -*-
import unittest

from xian_activities.merge import merge
from xian_activities.models import Activity


def make(name, **kwargs):
    defaults = dict(source="test", address="西安市雁塔区", highlights="一段活动介绍。")
    defaults.update(kwargs)
    return Activity(name=name, **defaults)


class MergeTest(unittest.TestCase):
    def test_adds_new_activity(self):
        existing = [make("老活动")]
        incoming = [make("新活动")]
        merged, stats = merge(existing, incoming)
        self.assertEqual(len(merged), 2)
        self.assertEqual(stats["added"], 1)
        self.assertTrue(any(item.seen_at for item in merged))

    def test_updates_mutable_fields_but_keeps_tags(self):
        old = make("秦腔演出", time_text="11月1日", price_text="免费")
        old.tags["categories"] = ["C"]
        old.tags["themes"] = ["秦腔"]
        old.enriched = {"model": "deepseek-flash", "hash": "abc"}
        old.scores["quality"] = 0.9

        fresh = make("秦腔演出", time_text="11月8日", price_text="80元", link="https://example.com/a")
        merged, stats = merge([old], [fresh])
        self.assertEqual(len(merged), 1)
        item = merged[0]
        self.assertEqual(item.time_text, "11月8日")
        self.assertEqual(item.link, "https://example.com/a")
        self.assertEqual(item.tags["themes"], ["秦腔"])
        self.assertEqual(item.enriched["model"], "deepseek-flash")
        self.assertEqual(item.scores["quality"], 0.9)
        self.assertEqual(stats["updated"], 1)

    def test_does_not_overwrite_known_price_with_unknown(self):
        old = make("活动", price_level="free")
        fresh = make("活动", price_level="unknown")
        merged, _ = merge([old], [fresh])
        self.assertEqual(merged[0].price_level, "free")

    def test_prunes_long_expired_activities(self):
        old = make("老展览", valid_end="2020-01-01")
        recent = make("新展览", valid_end="2099-01-01")
        merged, stats = merge([old, recent], [])
        self.assertEqual([item.name for item in merged], ["新展览"])
        self.assertEqual(stats["expired_removed"], 1)

    def test_keeps_undated_venues(self):
        venue = make("西安图书馆")
        merged, _ = merge([venue], [])
        self.assertEqual(len(merged), 1)


if __name__ == "__main__":
    unittest.main()
