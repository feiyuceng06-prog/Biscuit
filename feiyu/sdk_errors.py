"""Pure SDK error predicates shared by worker and parent; no configuration imports."""
import re

OVERFLOW_WORDS = re.compile(
    r"(token|context|prompt|input).{0,60}(exceed|too long|too large|limit|maximum)"
    r"|(exceed|maximum|too long|too large).{0,60}(token|context|length)", re.I | re.S)

_LIMIT_IN_ERROR = re.compile(
    r"(?:maximum|max|limit|上限)[^\d]{0,40}(\d{4,8})|(\d{4,8})\s*(?:tokens?\s*)?"
    r"(?:maximum|max|limit|上限)", re.I)
# 学到的上限再低也不低于这个 更低多半是把一次异常当成了窗口大小，
# 会让它之后每两轮就压缩一次
MIN_LEARNED_LIMIT = 16_000

