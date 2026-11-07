# -*- coding: utf-8 -*-
"""西安公共文化活动数据与智能推荐工具包。"""

from .models import Activity, SCHEMA_VERSION, dedupe, merge_tags  # noqa: F401
from .config import settings  # noqa: F401

__version__ = "2.0.0"
__all__ = ["Activity", "SCHEMA_VERSION", "dedupe", "merge_tags", "settings", "__version__"]
