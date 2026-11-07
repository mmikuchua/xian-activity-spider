# -*- coding: utf-8 -*-
"""问卷编码体系（与前端 web/assets/js/taxonomy.js 保持一致）。

问卷是「文享智配」的画像入口，所有活动标签最终都映射到这套编码上，
这样规则引擎与 LLM 打标才能对齐。
"""

from __future__ import annotations

from typing import Dict, List

# 活动类型 A-H（问卷第 7 题）
CATEGORIES: Dict[str, str] = {
    "A": "非遗手工",
    "B": "讲座沙龙",
    "C": "展览演出",
    "D": "阅读借阅",
    "E": "亲子活动",
    "F": "少儿艺术/科普/研学",
    "G": "老年文娱",
    "H": "公园/公共空间",
}

# 核心需求 A-D（问卷第 8 题）
DEMANDS: Dict[str, str] = {
    "A": "休闲放松",
    "B": "增长知识",
    "C": "社交陪伴",
    "D": "便民/技能",
}

# 舒适物类型 A-D（问卷第 9 题）
COMFORTS: Dict[str, str] = {
    "A": "公共I·文博馆",
    "B": "公共II·公园景点",
    "C": "市场I·书店艺术馆",
    "D": "市场II·特色街区",
}

# 关注因素 A-D（问卷第 10 题）
FACTORS: Dict[str, str] = {
    "A": "文化氛围",
    "B": "交通便利",
    "C": "免费/低费",
    "D": "环境优美",
}

# 年龄段 A-D（问卷第 1 题）
AGES: Dict[str, str] = {
    "A": "18岁以下",
    "B": "18-30岁",
    "C": "31-50岁",
    "D": "50岁以上",
}

# 可参与时段 A-D（问卷第 6 题；D 仅未成年）
TIME_SLOTS: Dict[str, str] = {
    "A": "工作日晚间",
    "B": "周末全天",
    "C": "随机空闲",
    "D": "寒暑假/节假日",
}

# 交通方式 A-D（问卷第 11 题）
TRAFFIC: Dict[str, str] = {
    "A": "公交",
    "B": "步行",
    "C": "自行车",
    "D": "自驾",
}

# 收入 A-D（问卷第 5 题）
INCOME: Dict[str, str] = {
    "A": "2000元以下",
    "B": "2000-4000元",
    "C": "4000-6000元",
    "D": "6000元以上",
}

PRICE_LEVELS: List[str] = ["free", "low", "medium", "high", "unknown"]

# 西安行政区（用于通勤估计）
DISTRICTS: List[str] = [
    "新城区", "碑林区", "莲湖区", "雁塔区", "灞桥区", "未央区",
    "长安区", "临潼区", "阎良区", "高陵区", "鄠邑区", "蓝田县",
    "周至县", "西咸新区", "曲江新区", "高新区", "浐灞生态区", "经开区",
]


def describe(code: str, table: Dict[str, str]) -> str:
    return table.get(code, "")


def taxonomy_prompt_block() -> str:
    """把编码体系渲染成提示词片段，保证 LLM 与规则引擎使用同一套标签。"""

    def lines(table: Dict[str, str]) -> str:
        return "；".join(f"{k}={v}" for k, v in table.items())

    return "\n".join(
        [
            f"活动类型 categories：{lines(CATEGORIES)}",
            f"核心需求 demand：{lines(DEMANDS)}",
            f"舒适物类型 comfort：{lines(COMFORTS)}",
            f"关注因素 factors：{lines(FACTORS)}",
            f"适合年龄 age_fit：{lines(AGES)}",
            f"可参与时段 time_slots：{lines(TIME_SLOTS)}",
            f"西安行政区 district 仅限：{', '.join(DISTRICTS)}",
        ]
    )
