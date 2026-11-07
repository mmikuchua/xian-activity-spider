# 西安公共文化活动 · 数据与 AI 推荐（xian-activities）

把「西安本地宝 / 陕西大剧院 / 陕西省图书馆」的活动信息抓下来，用 DeepSeek 做语义标注，
再以 API 的形式提供**可解释的活动推荐**。推荐结果直接喂给站点
[文享智配](https://mmikuchua.github.io/wenxiang-website/)（源码：
[wenxiang-website](https://github.com/mmikuchua/wenxiang-website)），也可以被 Coze / 扣子等工作流调用。

> 前身是一堆各跑各的脚本（`app.py`、`app_final.py`、`activity_api.py`、`1.py`、`420.py` …），
> 现在合并成一个包：抓取 → 清洗 → LLM 打标 → 导出 / API。

## 它做了什么

```
数据源                      流水线                         产物
┌──────────────┐   ┌─────────────────────────┐   ┌────────────────────┐
│ 西安本地宝    │   │ sources/*.py  抓取+解析   │   │ data/raw/*.json    │
│ 陕西大剧院    │──▶│ models.py     归一化去重   │──▶│ data/activities.json│──▶ 站点 / API
│ 陕西省图书馆  │   │ enrich.py     LLM 语义标注 │   └────────────────────┘
└──────────────┘   └─────────────────────────┘
```

- **语义标注**：每个活动补齐「适合谁、什么需求、什么时段、什么氛围、值不值得去」，
  以及一句 40 字以内的客观简介。规则标签（关键词字典）只作为兜底。
- **推荐**：`advisor.py` 先用字符 n-gram 召回 25 条候选，再让大模型在候选内重排并给出**逐条理由**。
  没有 API Key 或调用失败时自动降级为规则排序，接口不会 500。
- **缓存**：标注结果按内容哈希缓存在 `.cache/enrich/`，重复构建 0 次模型调用、秒级完成。

## 数据源

| 数据源 | 适配器 | 方式 | 说明 |
| --- | --- | --- | --- |
| 豆瓣同城 · 西安 | `sources/douban.py` | HTTP | 默认/售票/周末三个榜单，带档期、场馆、票价 |
| 活动行 · 西安 | `sources/huodongxing.py` | HTTP | 已用关键词过滤掉商业培训/行业会议，只留文化活动 |
| 西安本地宝 | `sources/bendibao_http.py` | HTTP | 活动日历 JSON 接口，最快最全；被人机验证挡住时自动跳过 |
| 西安本地宝（兜底） | `sources/bendibao.py` | 浏览器 | 本机 Selenium 抓取，适合被验证码拦截时手动补数据 |
| 陕西历史博物馆 | `sources/sxhm.py` | HTTP | 临时展览（含展期/展厅），自动过滤已结束的 |
| 陕西省图书馆 | `sources/sxlib.py` | HTTP | 陕图讲坛讲座预告 |
| 陕西大剧院 | `sources/snpac.py` | 浏览器 | SPA，需要本机 Chrome，CI 中跳过 |

- **HTTP 数据源**只依赖 `beautifulsoup4`，可以在 GitHub Actions 的服务器上跑；
- 单个源失败不会中断整批，报告里会写明失败原因；
- 抓取结果会做去重（名称+地址归一化）。

## 快速开始

```bash
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt

copy .env.example .env      # 填入 DEEPSEEK_API_KEY
python -m xian_activities.cli check        # 检查 API 连通性
python -m xian_activities.cli build        # 语义增强，生成 data/activities.json
python -m xian_activities.cli serve        # 启动 API：http://127.0.0.1:8000/docs
```

抓取与增量更新：

```bash
# 只跑 HTTP 数据源（CI 用的就是这一条）
python -m xian_activities.cli update --http-only

# 本机全量：加上陕西大剧院等需要浏览器的源
python -m xian_activities.cli update --all-sources

# 只看抓取结果，不打标
python -m xian_activities.cli crawl --source all --http-only --out data/raw/crawl.json
```

`update` 的流程是：抓取 → 与现有 `data/activities.json` 增量合并 → 只为新增/内容变更的活动调用模型 → 导出。
合并会保留已有标签，按内容哈希跳过未变化的条目；明确结束超过 90 天的活动会被淘汰。

> ⚠️ 西安本地宝有**拼图人机验证**，机房 IP 大概率被拦，被拦时会抛明确异常并保留旧数据。
> 建议在本机 `HEADLESS=0` 下用 `--all-sources` 补一次。

## HTTP API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 服务状态、模型配置、活动条数 |
| GET | `/api/activities?q=&limit=&category=&district=&free=` | 活动列表 / 关键词检索 |
| GET | `/api/activities/{id}` | 单条活动 |
| POST | `/api/recommend` | `{query, profile?, k?}` → AI 排序 + 理由 |
| POST | `/api/chat` | `{messages}` 或 `{query, profile?}` → 对话式推荐 |
| GET | `/api/stats` | 类型/区域/价格分布 |
| POST | `/api/refresh` | 抓取 + 重新标注（需 `ALLOW_CRAWL=true`，会跑几十秒） |

`/api/recommend` 示例：

```bash
curl -X POST http://127.0.0.1:8000/api/recommend ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"周末带孩子去免费的博物馆\",\"k\":3,\"profile\":{\"age\":\"C\",\"income\":\"B\",\"time\":\"B\"}}"
```

返回：

```json
{
  "reply": "按「免费博物馆 + 亲子研学」优先，推荐这三处，热门场馆记得提前预约。",
  "used_llm": true,
  "latency_ms": 8900,
  "items": [
    {"id": "act-...", "name": "西安博物院（小雁塔）", "reason": "免费开放，馆塔寺园一体…", "rank": 1}
  ]
}
```

## 数据结构（`activities.json`）

```jsonc
{
  "schema_version": 2,
  "generated_at": "2026-11-07T19:32:06+08:00",
  "count": 129,
  "activities": [
    {
      "id": "act-42fb2bd081",
      "name": "陕西省美术博物馆",
      "source": "西安公共文化场馆目录",
      "category_text": "文化展览",
      "summary": "西部地区唯一的美术博物馆…",
      "district": "碑林区",
      "price_level": "free",          // free | low | medium | high | unknown
      "price_from": 0,
      "tags": {
        "categories": ["C"],          // A-H，对应站点问卷第 7 题
        "demand": ["B"],              // A-D，核心需求
        "comfort": ["A"],             // A-D，空间类型
        "factors": ["A", "C"],        // A-D，关注因素
        "age_fit": ["B", "C", "D"],   // 适合年龄段
        "time_slots": ["A", "B"],     // 可参与时段
        "themes": ["美术", "展览"],    // LLM 主题词
        "moods": ["安静"],             // 现场氛围
        "audience": ["艺术爱好者"]      // 主要人群
      },
      "scores": {"culture": 0.9, "transport": 0.8, "quality": 0.85, "...": 0.5},
      "enriched": {"model": "deepseek-flash", "version": "2026-11-tag-v1", "at": "..."}
    }
  ]
}
```

字段与站点 `web/assets/js/engine.js` 一一对应，改字段时两边要一起改。

## 配置

全部通过环境变量（或 `.env`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 空 | 必填，否则只能离线清洗 |
| `DEEPSEEK_TAG_MODEL` | `deepseek-flash` | 打标用模型 |
| `DEEPSEEK_CHAT_MODEL` | `deepseek-flash` | 顾问/解释用模型，可换 `deepseek-v4-pro` |
| `ENRICH_CONCURRENCY` | `4` | 标注并发批次数 |
| `ENRICH_CACHE_DIR` | `.cache/enrich` | 标注缓存目录 |
| `ALLOW_CRAWL` | `true` | 是否允许 `/api/refresh` 触发抓取 |
| `CORS_ORIGINS` | `*` | 允许的来源，逗号分隔 |
| `HEADLESS` / `CHROME_BINARY` / `CHROMEDRIVER` | `1` / 自动 | 抓取时的浏览器设置 |

## 部署

```bash
docker build -t xian-activities .
docker run -p 8000:8000 --env-file .env xian-activities
```

也可以 `uvicorn xian_activities.server:app --host 0.0.0.0 --port 8000`，
或部署到任意支持 Python 的平台（见根目录 `render.yaml`）。

## 测试

```bash
python -m unittest discover -s tests -v     # 53 个用例，全部离线
```

覆盖：价格/行政区归一化、日期区间解析、增量合并与过期淘汰、LLM 输出清洗与跳过逻辑、
6 个数据源的 HTML/JSON 解析、AI 顾问召回与降级。

## 定时更新

定时任务放在站点仓库（因为它需要把结果提交成 `web/data/activities.json` 并发布 Pages）：
[`wenxiang-website/.github/workflows/refresh-data.yml`](https://github.com/mmikuchua/wenxiang-website/blob/main/.github/workflows/refresh-data.yml)

- 每天两次：UTC 20:23 / 08:23（北京时间 04:23 / 16:23）运行；
- 每次运行会 checkout 本仓库、抓取 HTTP 数据源、增量合并、只标注新增条目；
- 结果提交后直接部署到 GitHub Pages；
- 也可以在 Actions 页面手动触发，指定数据源与本次最多标注条数。

成本控制：未变化的条目按 `enriched.hash` 跳过，不会重复调用模型；`--max-enrich` 限制单次调用量。

## 目录

```
xian_activities/
  sources/        # douban / huodongxing / bendibao(_http) / sxhm / sxlib / snpac
  enrich.py       # LLM 打标提示词、批量并发、缓存、按内容哈希跳过
  merge.py        # 增量合并、字段更新、过期淘汰
  dates.py        # 中文日期区间 / 时间戳解析
  http.py         # 带重试与编码兜底的 HTTP 工具
  advisor.py      # 召回 + 大模型重排 + 规则兜底
  server.py       # FastAPI
  pipeline.py     # 加载 → 抓取 → 合并 → 增强 → 导出
  cli.py          # build / update / crawl / serve / check
tools/import_legacy.py   # 历史 SQLite 数据迁移
data/raw/                # 原始数据（可重放）
data/activities.json     # 站点直接消费的成品
```
