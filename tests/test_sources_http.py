# -*- coding: utf-8 -*-
"""HTTP 数据源解析测试：只吃 HTML/JSON 片段，不联网。"""

import unittest

from xian_activities.sources import bendibao_http, douban, huodongxing, sxhm

DOUBAN_HTML = """
<ul class="events-list">
  <li class="list-entry">
    <div class="pic"><a href="https://www.douban.com/event/34823662/">
      <img data-lazy="https://img3.doubanio.com/poster.jpg" src="blank.gif"></a></div>
    <div class="info">
      <div class="title"><a href="https://www.douban.com/event/34823662/" title="青曲社相声大会">
        <span itemprop="summary">青曲社相声大会</span></a></div>
      <ul class="event-meta">
        <li class="event-time"><span>时间：</span>11月07日 周六 19:30 ~ 11月29日 周日 19:35
          <time datetime="2026-11-07T19:30:00" itemprop="startDate"></time>
          <time datetime="2026-11-29T19:35:00" itemprop="endDate"></time></li>
        <li title="西安 碑林区 青曲社鼓楼剧场"><span>地点：</span>碑林区 青曲社鼓楼剧场
          <meta content="西安 碑林区 青曲社鼓楼剧场" itemprop="location"></li>
        <li class="fee"><span>费用：</span><strong>60.00元起</strong></li>
      </ul>
    </div>
  </li>
</ul>
"""

BENDIBAO_PAYLOAD = {
    "venue_info": {"648": {"name": "西安音乐厅", "address": "西安市雁塔区雁南一路"}},
    "activity_type": {"35": {"id": "35", "name": "演出演艺"}},
    "has_more": False,
    "res": [
        {
            "id": "36",
            "name": "2026 新年音乐会",
            "venue_id": "648",
            "type_id": "35",
            "heighlight": "一年一度的新年音乐会",
            "pcurl": "http://xa.bendibao.com/xiuxian/2024419/127648.shtm",
            "image": "https://img.example/poster.jpg",
            "dates": {"2424": {"start_date": "1767196800", "end_date": "1767373200"}},
        }
    ],
}

SXHM_HTML = """
<div class="item">
  <a class="pic" href="/Temporary/detail/1018653.html"><img class="i" src="/Uploads/x.jpg"></a>
  <div class="text">
    <a class="t1" href="/Temporary/detail/1018653.html">锦绣华裳——古代服饰精品展</a>
    <div class="t2">
      <div class="p">时间：2026年7月6日至10月11日</div>
      <div class="p">地点：陕西历史博物馆第五展厅</div>
    </div>
  </div>
</div>
"""

HDX_HTML = """
<div class="search-tab-content-item-mesh">
  <a href="/event/1885660525600"><img class="item-logo" src="https://cdn/p.jpg"></a>
  <div class="item-mesh-conter">
    <a class="item-title" href="/event/1885660525600">
      <img src="x.png"><span>曲艺相声《妙语连珠》</span></a>
    <div class="item-dress">
      <p>11/21 周六 ~ 11/22 周日</p>
      <span><span class="item-dress-pp">陕西西安</span></span>
    </div>
  </div>
</div>
"""


class DoubanTest(unittest.TestCase):
    def test_parse(self):
        activities = douban.parse_events(DOUBAN_HTML)
        self.assertEqual(len(activities), 1)
        item = activities[0]
        self.assertEqual(item.name, "青曲社相声大会")
        self.assertEqual(item.address, "碑林区 青曲社鼓楼剧场")
        self.assertEqual(item.price_text, "60.00元起")
        self.assertTrue(item.valid_start.startswith("2026-11-07T19:30"))
        self.assertTrue(item.valid_end.startswith("2026-11-29T19:35"))
        self.assertEqual(item.source, "豆瓣同城")

    def test_empty(self):
        self.assertEqual(douban.parse_events("<html></html>"), [])


class BendibaoHttpTest(unittest.TestCase):
    def test_parse_payload(self):
        activities = bendibao_http.parse_payload(BENDIBAO_PAYLOAD)
        self.assertEqual(len(activities), 1)
        item = activities[0]
        self.assertEqual(item.name, "2026 新年音乐会")
        self.assertIn("西安音乐厅", item.address)
        self.assertEqual(item.category_text, "演出演艺")
        self.assertEqual(item.link, "https://xa.bendibao.com/xiuxian/2024419/127648.shtm")
        self.assertTrue(item.valid_start.startswith("2026-01"))
        self.assertTrue(item.valid_end.startswith("2026-01"))

    def test_missing_name_skipped(self):
        payload = {"res": [{"id": "1"}], "venue_info": {}, "activity_type": {}}
        self.assertEqual(bendibao_http.parse_payload(payload), [])


class SxhmTest(unittest.TestCase):
    def test_parse_exhibitions(self):
        activities = sxhm.parse_exhibitions(SXHM_HTML)
        self.assertEqual(len(activities), 1)
        item = activities[0]
        self.assertEqual(item.name, "锦绣华裳——古代服饰精品展")
        self.assertEqual(item.address, "陕西历史博物馆第五展厅")
        self.assertTrue(item.valid_start.startswith("2026-07-06"))
        self.assertTrue(item.valid_end.startswith("2026-10-11"))
        self.assertEqual(item.tags["categories"], ["C"])


class HuodongxingTest(unittest.TestCase):
    def test_parse(self):
        activities = huodongxing.parse_events(HDX_HTML)
        self.assertEqual(len(activities), 1)
        item = activities[0]
        self.assertEqual(item.name, "曲艺相声《妙语连珠》")
        self.assertEqual(item.address, "陕西西安")
        self.assertTrue(item.valid_start)

    def test_culture_filter(self):
        self.assertTrue(huodongxing.is_cultural("曲艺相声《妙语连珠》"))
        self.assertTrue(huodongxing.is_cultural("西安 | 芭蕾舞《天鹅湖》"))
        self.assertFalse(huodongxing.is_cultural("西安线下小班AI办公培训"))
        self.assertFalse(huodongxing.is_cultural("2026 陕西阳光建企共创伙伴计划"))
        self.assertFalse(huodongxing.is_cultural("西北火锅产业大会"))


if __name__ == "__main__":
    unittest.main()
