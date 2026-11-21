"""
心理关怀模块的 Module API。

其他模块如果需要“评估情绪 / 查画像 / 查预警”，只能走这里。
"""

from __future__ import annotations

from app.psych.internal.service import (
    assess_emotion,
    get_profile,
    list_alerts,
    log_conversation,
    update_alert,
)

__all__ = [
    "assess_emotion",
    "get_profile",
    "list_alerts",
    "update_alert",
    "log_conversation",
]
