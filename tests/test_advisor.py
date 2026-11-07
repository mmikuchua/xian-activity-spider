# -*- coding: utf-8 -*-
"""AI 顾问测试：召回、降级、理由生成（不联网）。"""

import unittest
from unittest import mock

from xian_activities.advisor import Advisor, lexical_score
from xian_activities.config import settings
from xian_activities.models import Activity


def build_activities():
    return [
        Activity(
            name="易俗社秦腔专场",
            source="test",
            district="碑林区",
            price_text="免费",
            summary="百年易俗社的秦腔经典折子戏，现场有讲解。",
            tags={"categories": ["C"], "themes": ["秦腔", "戏曲"], "demand": ["A"], "time_slots": ["B"]},
        ),
        Activity(
            name="陕西历史博物馆",
            source="test",
            district="雁塔区",
            price_text="免费",
            summary="周秦汉唐文物常设展，适合带孩子看。",
            tags={"categories": ["C"], "themes": ["博物馆", "历史"], "demand": ["B"], "time_slots": ["A", "B"]},
        ),
        Activity(
            name="亲子手作工坊",
            source="test",
            district="雁塔区",
            price_text="80元",
            summary="亲子手作体验，适合 6 岁以上儿童。",
            tags={"categories": ["A", "E"], "themes": ["手工", "亲子"], "demand": ["C"], "time_slots": ["B"]},
        ),
    ]


class LexicalTest(unittest.TestCase):
    def test_query_hits_relevant_activity(self):
        activities = build_activities()
        scores = [lexical_score("想听秦腔", activity) for activity in activities]
        self.assertEqual(max(range(len(scores)), key=lambda index: scores[index]), 0)

    def test_empty_query_scores_zero(self):
        self.assertEqual(lexical_score("", build_activities()[0]), 0.0)


class RecallTest(unittest.TestCase):
    def test_recall_orders_by_relevance(self):
        advisor = Advisor(build_activities())
        recalled = advisor.recall("带孩子看博物馆", k=3)
        self.assertEqual(recalled[0].name, "陕西历史博物馆")

    def test_k_limits(self):
        advisor = Advisor(build_activities())
        self.assertLessEqual(len(advisor.recall("免费", k=1)), 1)


class FallbackTest(unittest.TestCase):
    def setUp(self):
        self._api_key = settings.api_key

    def tearDown(self):
        settings.api_key = self._api_key

    def test_without_api_key_returns_rule_based_picks(self):
        settings.api_key = ""
        advisor = Advisor(build_activities())
        result = advisor.recommend("周末带孩子做手工", k=2)
        self.assertFalse(result.used_llm)
        self.assertEqual(len(result.picks), 2)
        self.assertTrue(all(pick["reason"] for pick in result.picks))
        self.assertTrue(result.reply)

    def test_llm_failure_falls_back(self):
        settings.api_key = "sk-test"
        advisor = Advisor(build_activities())
        with mock.patch.object(advisor.client, "chat_json", side_effect=RuntimeError("网络挂了")):
            with mock.patch("xian_activities.advisor.LLMError", RuntimeError):
                result = advisor.recommend("想听秦腔", k=2)
        self.assertFalse(result.used_llm)
        self.assertTrue(result.picks)

    def test_invalid_ids_are_dropped(self):
        advisor = Advisor(build_activities())
        result = advisor._normalize_picks(
            {"reply": "ok", "picks": [{"id": "act-nope", "reason": "编的"}, {"id": build_activities()[0].id, "reason": "合适"}]},
            build_activities(),
            3,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["reason"], "合适")


if __name__ == "__main__":
    unittest.main()
