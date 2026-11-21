"""
画像研判与推荐模块的 Module API。

其他模块（Dify 工具）通过 HTTP 调用；Python 内部模块如需推荐，走这里。
"""

from __future__ import annotations

from app.recommend.internal.service import recommend

__all__ = ["recommend"]
