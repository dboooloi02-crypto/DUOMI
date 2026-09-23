import os
import json
import hashlib
from difflib import SequenceMatcher

IMPORTANT_MEMORY_FILE = "important_memory.json"


def load_important_memory():
    if os.path.exists(IMPORTANT_MEMORY_FILE):
        with open(IMPORTANT_MEMORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return normalize_all_memories(data)

    return []

def save_important_memory(memories):
    with open(IMPORTANT_MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memories, file, ensure_ascii=False, indent=2)


def make_memory_id(memory):
    raw = (
        memory.get("type", "")
        + "|"
        + memory.get("content", "")
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:12]


def normalize_memory(memory):
    if "id" not in memory:
        memory["id"] = make_memory_id(memory)

    if "status" not in memory:
        memory["status"] = "active"

    if "importance" not in memory:
        memory["importance"] = "normal"

    if "related_to" not in memory:
        memory["related_to"] = []

    return memory

def normalize_all_memories(memories):
    result = []

    for memory in memories:
        if isinstance(memory, dict):
            result.append(normalize_memory(memory))

    return result

def add_memory(memory, memories):
    memory = normalize_memory(memory)

    for existing in memories:
        if existing["id"] == memory["id"]:
            existing_related = existing.get("related_to", [])
            new_related = memory.get("related_to", [])

            for related_id in new_related:
                if related_id not in existing_related:
                    existing_related.append(related_id)

            existing["related_to"] = existing_related

            save_important_memory(memories)
            return memories

    memories.append(memory)
    save_important_memory(memories)

    return memories

def update_memory(memory_id, new_data, memories):
    for memory in memories:
        if memory.get("id") == memory_id:
            memory.update(new_data)
            memory["id"] = memory_id
            memory["status"] = "active"

            save_important_memory(memories)
            return memories

    return memories

def archive_memory(memory_id, memories):
    for memory in memories:
        if memory.get("id") == memory_id:
            memory["status"] = "archived"

            save_important_memory(memories)
            return memories

    return memories


def link_memories(memory_id_a, memory_id_b, memories):
    if memory_id_a == memory_id_b:
        return memories

    memory_a = None
    memory_b = None

    for memory in memories:
        if memory.get("id") == memory_id_a:
            memory_a = memory

        if memory.get("id") == memory_id_b:
            memory_b = memory

    if memory_a is None or memory_b is None:
        return memories

    if "related_to" not in memory_a:
        memory_a["related_to"] = []

    if "related_to" not in memory_b:
        memory_b["related_to"] = []

    if memory_id_b not in memory_a["related_to"]:
        memory_a["related_to"].append(memory_id_b)

    if memory_id_a not in memory_b["related_to"]:
        memory_b["related_to"].append(memory_id_a)

    save_important_memory(memories)

    return memories


def get_active_memories(memories):
    return [
        memory
        for memory in memories
        if memory.get("status") == "active"
    ]


def get_related_memories(memory, memories, limit=5):
    related_ids = memory.get("related_to", [])

    if not related_ids:
        return []

    results = []

    for item in memories:
        if item.get("status") != "active":
            continue

        if item.get("id") in related_ids:
            results.append(item)

    return results[:limit]


# ============================================================
# DUOMI Memory Retrieval V3
# ============================================================

from difflib import SequenceMatcher
import re


# ------------------------------------------------------------
# 同义表达归一化
# ------------------------------------------------------------

ALIASES = {
    "陪着": "陪伴",
    "陪着我生活": "陪伴生活",
    "陪我生活": "陪伴生活",
    "和我一起生活": "生活",
    "跟我一起生活": "生活",
    "一起生活": "生活",

    "做决定": "判断",
    "自己观察": "观察",
    "独立观察": "观察",

    "做出来": "创造者",
    "谁做的": "创造者",
    "谁做出来的": "创造者",

    "会说话": "说话",
    "能说话": "说话",
    "会不会说话": "说话",

    "叫什么名字": "名字",
    "姓名是什么": "名字",
}


# ------------------------------------------------------------
# 只过滤“完整词/短语”
#
# 不再直接删除单个“能”“会”“我”等字符。
# 防止：
#   功能 -> 功
#   社会 -> 社
#   能力 -> 力
# 之类的问题。
# ------------------------------------------------------------

STOP_BIGRAMS = {
    "多米",
    "用户",
    "以后",
    "将来",
    "未来",
    "现在",
    "目前",
    "当前",
    "已经",
    "希望",
    "想要",
    "能够",
    "可以",
    "能不能",
    "是不是",
    "是否",
    "有没有",
    "一起",
    "自己",
    "什么",
    "谁",
    "我的",
    "你的",
}


def normalize_text(text):
    text = str(text).lower().strip()

    # 同义表达先归一化
    for old, new in sorted(
        ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True
    ):
        text = text.replace(old.lower(), new)

    # 去标点，但保留中文字符本身
    text = re.sub(
        r"[\s，。！？、,.!?：；;（）()“”‘’\"'《》【】\[\]…]",
        "",
        text
    )

    return text


def get_bigrams(text):
    if not text:
        return set()

    if len(text) < 2:
        return set()

    return {
        text[i:i + 2]
        for i in range(len(text) - 1)
        if text[i:i + 2] not in STOP_BIGRAMS
    }


def fuzzy_similarity(query, content):
    query = normalize_text(query)
    content = normalize_text(content)

    if not query or not content:
        return 0.0

    if query in content:
        return 1.0

    query_length = len(query)

    if len(content) <= query_length:
        return SequenceMatcher(
            None,
            query,
            content
        ).ratio()

    best_score = 0.0

    for i in range(
        len(content) - query_length + 1
    ):
        window = content[
            i:i + query_length
        ]

        score = SequenceMatcher(
            None,
            query,
            window
        ).ratio()

        if score > best_score:
            best_score = score

    return best_score


def _build_document_frequency(memories):
    document_frequency = {}

    for memory in memories:

        if memory.get("status") != "active":
            continue

        content = normalize_text(
            memory.get("content", "")
        )

        for bigram in get_bigrams(content):
            document_frequency[bigram] = (
                document_frequency.get(bigram, 0) + 1
            )

    return document_frequency


def _score_memory(
    query,
    memory,
    document_frequency
):
    original_query = str(query).lower().strip()

    original_content = str(
        memory.get("content", "")
    ).lower()

    normalized_query = normalize_text(query)
    normalized_content = normalize_text(
        original_content
    )

    if not normalized_query:
        return 0.0, 0.0, []

    score = 0.0
    reasons = []

    # ========================================================
    # 1. 原文完整匹配
    # ========================================================

    if (
        original_query
        and original_query in original_content
    ):
        score += 8.0
        reasons.append("原文完整匹配")

    # ========================================================
    # 2. 归一化完整短语
    # ========================================================

    if (
        len(normalized_query) >= 2
        and normalized_query in normalized_content
    ):
        score += 6.0
        reasons.append("归一化短语匹配")

    # ========================================================
    # 3. 中文二字词匹配
    # ========================================================

    query_bigrams = get_bigrams(
        normalized_query
    )

    content_bigrams = get_bigrams(
        normalized_content
    )

    matched = (
        query_bigrams
        & content_bigrams
    )

    for bigram in matched:

        df = document_frequency.get(
            bigram,
            0
        )

        if df == 1:
            weight = 3.0
        elif df == 2:
            weight = 1.5
        elif df == 3:
            weight = 0.7
        else:
            weight = 0.2

        score += weight

    if matched:
        reasons.append(
            "关键词：" +
            ",".join(sorted(matched))
        )

    # ========================================================
    # 4. 模糊匹配
    # ========================================================

    fuzzy = fuzzy_similarity(
        query,
        original_content
    )

    if fuzzy >= 0.35:
        score += fuzzy * 2.0
        reasons.append(
            f"fuzzy={fuzzy:.3f}"
        )

    base_score = score

    # ========================================================
    # 5. 时间语境
    #
    # 非常重要：
    # 只有已经相关的记忆，才允许时间语境加减分。
    # ========================================================

    if base_score > 0:

        query_is_current = any(
            marker in original_query
            for marker in (
                "现在",
                "目前",
                "当前"
            )
        )

        query_is_future = any(
            marker in original_query
            for marker in (
                "以后",
                "未来",
                "将来"
            )
        )

        content_is_future = any(
            marker in original_content
            for marker in (
                "以后",
                "未来",
                "将来"
            )
        )

        content_is_current = any(
            marker in original_content
            for marker in (
                "现在",
                "目前",
                "当前"
            )
        )

        if query_is_current:
            if (
                content_is_future
                and not content_is_current
            ):
                score -= 3.0
                reasons.append("未来记忆降权")

        if query_is_future:
            if content_is_future:
                score += 2.0
                reasons.append("未来记忆加权")

    # ========================================================
    # 6. 语音能力专项判断
    # ========================================================

    speech_question = (
        "会说话" in original_query
        or "能说话" in original_query
        or "说话吗" in original_query
    )

    if speech_question and base_score > 0:

        if (
            "tts" in original_content
            or "能够说话" in original_content
            or "使duomi能够说话"
            in original_content.replace(" ", "")
        ):
            score += 4.0
            reasons.append("语音能力匹配")

        if (
            "学会听" in original_content
            or "学着理解" in original_content
        ):
            score -= 2.0
            reasons.append("听觉学习记忆降权")

    return score, fuzzy, reasons


def _is_direct_match(
    score,
    base_score
):
    # 必须有真实内容相关性。
    # 单纯“以后”“用户”“多米”等词不能形成召回。
    return (
        base_score >= 2.0
        and score >= 2.0
    )


def retrieve_memories(
    query,
    memories,
    limit=5
):
    if not query:
        return []

    if not memories:
        return []

    document_frequency = (
        _build_document_frequency(memories)
    )

    direct_results = []

    # ========================================================
    # 第一阶段：直接相关记忆
    # ========================================================

    for memory in memories:

        if memory.get("status") != "active":
            continue

        score, fuzzy, reasons = (
            _score_memory(
                query,
                memory,
                document_frequency
            )
        )

        # 重新计算基础相关性，
        # 用于禁止“只有时间词”的误召回。
        original_query = (
            str(query)
            .lower()
            .strip()
        )

        original_content = str(
            memory.get("content", "")
        ).lower()

        normalized_query = normalize_text(
            query
        )

        normalized_content = normalize_text(
            original_content
        )

        base_score = 0.0

        if (
            original_query
            and original_query in original_content
        ):
            base_score += 8.0

        if (
            len(normalized_query) >= 2
            and normalized_query in normalized_content
        ):
            base_score += 6.0

        query_bigrams = get_bigrams(
            normalized_query
        )

        content_bigrams = get_bigrams(
            normalized_content
        )

        matched = (
            query_bigrams
            & content_bigrams
        )

        for bigram in matched:

            df = document_frequency.get(
                bigram,
                0
            )

            if df == 1:
                base_score += 3.0
            elif df == 2:
                base_score += 1.5
            elif df == 3:
                base_score += 0.7
            else:
                base_score += 0.2

        fuzzy = fuzzy_similarity(
            query,
            original_content
        )

        if fuzzy >= 0.35:
            base_score += fuzzy * 2.0

        if not _is_direct_match(
            score,
            base_score
        ):
            continue

        direct_results.append(
            {
                "score": score,
                "fuzzy": fuzzy,
                "base_score": base_score,
                "memory": memory,
                "reasons": reasons,
            }
        )

    direct_results.sort(
        key=lambda item: (
            item["score"],
            item["base_score"],
            item["fuzzy"]
        ),
        reverse=True
    )

    # ========================================================
    # 第二阶段：直接结果
    # ========================================================

    selected = []

    seen_ids = set()

    for item in direct_results[:limit]:

        memory = item["memory"]
        memory_id = memory.get("id")

        if memory_id in seen_ids:
            continue

        selected.append(memory)
        seen_ids.add(memory_id)

    # ========================================================
    # 第三阶段：受控关联扩展
    #
    # 只有：
    # 1. 已经是强直接命中
    # 2. 被关联的记忆本身也有一定相关性
    #
    # 才允许加入。
    # ========================================================

    if len(selected) < limit:

        strong_direct = [
            item
            for item in direct_results
            if item["score"] >= 6.0
        ]

        # 最多从前两个强命中节点扩展
        for item in strong_direct[:2]:

            source_memory = item["memory"]

            related_memories = (
                get_related_memories(
                    source_memory,
                    memories,
                    limit=5
                )
            )

            for related in related_memories:

                related_id = related.get("id")

                if related_id in seen_ids:
                    continue

                related_score, related_fuzzy, _ = (
                    _score_memory(
                        query,
                        related,
                        document_frequency
                    )
                )

                # 关联记忆自己也必须有一定主题相关性
                if related_score < 2.0:
                    continue

                selected.append(related)
                seen_ids.add(related_id)

                if len(selected) >= limit:
                    break

            if len(selected) >= limit:
                break

    return selected[:limit]
