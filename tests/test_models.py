# -*- coding: utf-8 -*-
import unittest

from xian_activities.models import Activity, dedupe, infer_district, normalize_price_level, price_from_text


def make(**kwargs):
    defaults = dict(name="测试活动", source="test", address="西安市雁塔区小寨东路")
    defaults.update(kwargs)
    return Activity(**defaults)


class PriceTest(unittest.TestCase):
    def test_free_keywords(self):
        for text in ["免费", "公益开放", "0元", "惠民演出", "免票入场"]:
            self.assertEqual(normalize_price_level(text), "free", text)

    def test_levels(self):
        self.assertEqual(normalize_price_level("30元"), "low")
        self.assertEqual(normalize_price_level("80-120元"), "medium")
        self.assertEqual(normalize_price_level("380元起"), "high")
        self.assertEqual(normalize_price_level("价格待定"), "unknown")
        self.assertEqual(normalize_price_level("未获取"), "unknown")

    def test_price_from(self):
        self.assertEqual(price_from_text("免费"), 0.0)
        self.assertEqual(price_from_text("80-120元"), 80.0)
        self.assertIsNone(price_from_text("面议"))


class DistrictTest(unittest.TestCase):
    def test_landmark_wins_over_road_name(self):
        # 「长安路」不是「长安区」
        self.assertEqual(infer_district("陕西省图书馆（长安路馆区）"), "碑林区")

    def test_full_district_name(self):
        self.assertEqual(infer_district("西安市雁塔区大唐不夜城"), "雁塔区")

    def test_unknown(self):
        self.assertEqual(infer_district("某个没写清的地方"), "")


class ActivityTest(unittest.TestCase):
    def test_post_init_normalizes(self):
        activity = make(price_text="免费（公益）", address="西安市莲湖区")
        self.assertEqual(activity.price_level, "free")
        self.assertEqual(activity.price_from, 0.0)
        self.assertEqual(activity.district, "莲湖区")
        self.assertTrue(activity.id.startswith("act-"))

    def test_roundtrip(self):
        activity = make(price_text="60元")
        restored = Activity.from_dict(activity.to_dict())
        self.assertEqual(restored.id, activity.id)
        self.assertEqual(restored.price_level, "medium")
        self.assertEqual(restored.name, activity.name)

    def test_validate_flags_missing_name(self):
        activity = Activity(name="", source="test")
        self.assertIn("缺少活动名称", activity.validate())

    def test_validate_rejects_bad_code(self):
        activity = make(tags={"categories": ["Z"]})
        self.assertTrue(any("未知编码" in problem for problem in activity.validate()))

    def test_dedupe_keeps_richer_record(self):
        sparse = make(name="同名活动", highlights="")
        rich = make(name="同名活动", highlights="这是一段更完整的活动亮点介绍，长度足够。")
        result = dedupe([sparse, rich])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].highlights)


if __name__ == "__main__":
    unittest.main()
