# -*- coding: utf-8 -*-
"""时间状态判定 —— 插件自己的「放学后」判断（不改主程序的状态）。

规则（用户约定）：
1. 一天里相邻的「课程/课间」之间的空档超过 1 小时 → 空档内算放学后；
2. 当天一条课程/课间都没有 → 一整天都算放学后；
3. 参与判定的条目类型只有 class（课程）与 break（课间）；
   活动 activity / 预备 preparation / 空闲 free 不参与，
   所以它们夹着的长空档不会被误判成放学。

这个模块不依赖 PySide6，可以直接单测。
"""

from __future__ import annotations

import re

# 空档超过这个分钟数就算放学后
GAP_MINUTES = 60
# 参与判定的条目类型：课程、课间
STUDY_TYPES = ("class", "break")
HOST_FREE = "free"


def hhmm_to_minutes(value) -> int:
    """把 "HH:MM" 转成分钟数；解析不了返回 -1。"""
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(value or "").strip())
    if not m:
        return -1
    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return -1
    return hour * 60 + minute


def study_entries(entries) -> list:
    """挑出参与判定的课程/课间，并按开始时间排序。"""
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("type") or "") not in STUDY_TYPES:
            continue
        out.append(entry)
    return sorted(out, key=lambda e: hhmm_to_minutes(e.get("startTime")))


def long_gaps(entries) -> list:
    """相邻课程/课间之间的长空档，返回 [(开始分钟, 结束分钟), ...]。"""
    gaps = []
    study = study_entries(entries)
    for left, right in zip(study, study[1:]):
        end = hhmm_to_minutes(left.get("endTime"))
        start = hhmm_to_minutes(right.get("startTime"))
        if end < 0 or start < 0 or start <= end:
            continue
        if start - end > GAP_MINUTES:
            gaps.append((end, start))
    return gaps


def is_after_school(entries, now_minutes: int) -> bool:
    """此刻是否算放学后。

    除了「长空档」，最后一节课程/课间结束之后也算放学后
    （当天已经没有别的课了）；第一节课之前不算。
    """
    study = study_entries(entries)
    if not study:
        return True
    for start, end in long_gaps(entries):
        if start <= now_minutes < end:
            return True
    last_end = hhmm_to_minutes(study[-1].get("endTime"))
    if last_end >= 0 and now_minutes >= last_end:
        return True
    return False


def effective_status(host_status, entries, now_minutes: int) -> str:
    """插件视角下的时间状态。

    非空闲一律沿用主程序的说法；主程序说空闲时再用「长空档」确认：
    确实是放学后就是 free，只是普通空档则算 break（课间）。
    这样「当前时间状态是 放学后」这类规则不会在课间空当里误触发。
    """
    status = str(host_status or HOST_FREE)
    if status != HOST_FREE:
        return status
    return HOST_FREE if is_after_school(entries, now_minutes) else "break"
