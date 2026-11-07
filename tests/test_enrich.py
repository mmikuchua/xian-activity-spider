# -*- coding: utf-8 -*-
import unittest

from xian_activities.enrich import completeness_score, sanitize_enrichment
from xian_activities.models import Activity, merge_tags


class SanitizeTest(unittest.TestCase):
    def test_clamps_invalid_codes(self):
        cleaned = sanitize_enrichment(
            {
                "categories": ["C", "Z", "c", "H", "A", "B"],
                "demand": ["A", "Q"],
                "comfort": ["A", "B", "C"],
                "age_fit": ["A", "B", "C", "D", "X"],
                "time_slots": ["B", "Z"],
                "themes": ["秦腔", "  ", "非遗", "秦腔"],
                "moods": ["热闹"],
                "audience": ["本地居民"],
                "price_level": "FREE",
                "price_from": "-5",
                "district": "雁塔",
                "summary": " 简介 ",
                "scores": {"culture": 1.5, "transport": -1, "unknown": 0.5},
            }
        )
        self.assertEqual(cleaned["categories"], ["C", "H", "A"])
        self.assertEqual(cleaned["demand"], ["A"])
        self.assertEqual(cleaned["comfort"], ["A", "B"])
        self.assertEqual(cleaned["age_fit"], ["A", "B", "C", "D"])
        self.assertEqual(cleaned["themes"], ["秦腔", "非遗"])
        self.assertEqual(cleaned["price_level"], "free")  # 大小写归一
        self.assertEqual(cleaned["price_from"], 0.0)
        self.assertEqual(cleaned["district"], "雁塔区")
        self.assertEqual(cleaned["scores"], {"culture": 1.0, "transport": 0.0})

    def test_invalid_price_level_falls_back(self):
        cleaned = sanitize_enrichment({"price_level": "很便宜"})
        self.assertEqual(cleaned["price_level"], "unknown")

    def test_missing_fields_fall_back(self):
        cleaned = sanitize_enrichment({})
        self.assertEqual(cleaned["categories"], [])
        self.assertEqual(cleaned["price_level"], "unknown")
        self.assertIsNone(cleaned["price_from"])
        self.assertEqual(cleaned["summary"], "")

    def test_bad_types_do_not_raise(self):
        cleaned = sanitize_enrichment({"categories": "C", "themes": 42, "scores": "nope"})
        # 模型有时把数组写成字符串：宽容接受单个编码
        self.assertEqual(cleaned["categories"], ["C"])
        self.assertEqual(cleaned["themes"], [])
        self.assertEqual(cleaned["scores"], {})


class MergeTest(unittest.TestCase):
    def test_llm_tags_win_but_missing_fields_fall_back(self):
        merged = merge_tags(
            {"categories": ["C"], "themes": [], "demand": []},
            {"categories": ["A"], "themes": ["秦腔"], "demand": ["B"]},
        )
        self.assertEqual(merged["categories"], ["C"])
        self.assertEqual(merged["themes"], ["秦腔"])
        self.assertEqual(merged["demand"], ["B"])


class CompletenessTest(unittest.TestCase):
    def test_richer_activity_scores_higher(self):
        bare = Activity(name="空壳", source="test")
        rich = Activity(
            name="完整",
            source="test",
            address="西安市碑林区",
            price_text="免费",
            time_text="周末全天",
            highlights="这是一段足够长的活动介绍，用来测试信息完整度的计算是否正确。",
            link="https://example.com",
        )
        self.assertGreater(completeness_score(rich), completeness_score(bare))


if __name__ == "__main__":
    unittest.main()
