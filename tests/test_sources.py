# -*- coding: utf-8 -*-
"""数据源解析测试：只吃 HTML 片段，不联网、不启动浏览器。"""

import unittest

from xian_activities.sources import bendibao, snpac, sxlib

BENDIBAO_HTML = """
<div class="main-block-single">
  <div class="main-single-block-titles">秦腔经典折子戏专场</div>
  <div class="time-dia-hover">2026-03-01 19:30</div>
  <div class="main-single-block-msg">
    <span class="main-single-block-des">活动地址：</span><span>易俗社文化街区</span>
  </div>
  <div class="main-single-block-msg">
    <span class="main-single-block-des">活动亮点：</span><span>经典折子戏连演，现场有讲解。</span>
  </div>
  <a class="ticket-buttons" href="/xiuxian/2026/0301/123.shtml">查看攻略</a>
</div>
<div class="main-block-single">
  <div class="main-single-block-titles">春日市集</div>
  <div class="time-dia-hover">周末全天</div>
  <div class="main-single-block-msg">
    <span class="main-single-block-des">活动地址：</span><span>老菜场市井文化创意街区</span>
  </div>
  <a class="ticket-buttons" href="https://example.com/a">查看攻略</a>
</div>
"""

SXLIB_HTML = """
<ul id="zebra">
  <li><a href="/hd/hdyg/stjt/202603/t20260301_1.html"><font>长安与丝绸之路</font></a>
      <span>2026-03-05 14:30</span></li>
  <li><a href="https://www.sxlib.org.cn/hd/hdyg/stjt/2.html"><font>唐诗里的长安</font></a>
      <span>2026-03-12 14:30</span></li>
</ul>
"""

SNPAC_HTML = """
<div class="program-item">
  <h3 class="program-name">话剧《白鹿原》</h3>
  <span class="tip-text">话剧</span>
  <span class="address">陕西大剧院·歌剧厅</span>
  <span class="price-part">180-680元</span>
  <span class="year">2026-03-20</span>
  <a href="/ticket/detail/123.html">购票</a>
</div>
"""


class BendibaoParseTest(unittest.TestCase):
    def test_parse_fields(self):
        activities = bendibao.parse_list(BENDIBAO_HTML)
        self.assertEqual(len(activities), 2)
        first = activities[0]
        self.assertEqual(first.name, "秦腔经典折子戏专场")
        self.assertEqual(first.time_text, "2026-03-01 19:30")
        self.assertEqual(first.address, "易俗社文化街区")
        self.assertIn("折子戏", first.highlights)
        self.assertTrue(first.link.startswith("https://xa.bendibao.com/xiuxian/2026"))
        self.assertEqual(first.source, "西安本地宝")

    def test_absolute_link_kept(self):
        activities = bendibao.parse_list(BENDIBAO_HTML)
        self.assertEqual(activities[1].link, "https://example.com/a")

    def test_captcha_is_reported(self):
        with self.assertRaises(RuntimeError):
            bendibao._assert_not_captcha("<title>请完成拼图验证以继续访问</title>")

    def test_empty_html(self):
        self.assertEqual(bendibao.parse_list("<html></html>"), [])


class SxlibParseTest(unittest.TestCase):
    def test_parse_fields(self):
        activities = sxlib.parse_list(SXLIB_HTML)
        self.assertEqual(len(activities), 2)
        first = activities[0]
        self.assertEqual(first.name, "长安与丝绸之路")
        self.assertEqual(first.time_text, "2026-03-05 14:30")
        self.assertEqual(first.source, "陕西省图书馆")
        self.assertEqual(first.tags["categories"], ["B"])
        self.assertTrue(first.link.endswith("20260301_1.html"))

    def test_missing_list(self):
        self.assertEqual(sxlib.parse_list("<html></html>"), [])


class SnpacParseTest(unittest.TestCase):
    def test_parse_fields(self):
        activities = snpac.parse_cards(SNPAC_HTML)
        self.assertEqual(len(activities), 1)
        item = activities[0]
        self.assertEqual(item.name, "话剧《白鹿原》")
        self.assertEqual(item.category_text, "话剧")
        self.assertEqual(item.address, "陕西大剧院·歌剧厅")
        self.assertEqual(item.price_level, "high")
        self.assertEqual(item.source, "陕西大剧院")

    def test_empty_html(self):
        self.assertEqual(snpac.parse_cards("<html></html>"), [])


if __name__ == "__main__":
    unittest.main()
