from copy import deepcopy
import json
from openai import OpenAI
import os
import re
from datetime import datetime
from difflib import SequenceMatcher


IMAGINATION_FILE = "imagination_memory.json"
# =========================================================
# DUOMI Imagination 全局 DeepSeek Client
# =========================================================

_imagination_api_key = os.environ.get("DEEPSEEK_API_KEY")

if not _imagination_api_key:
    raise RuntimeError(
        "❌ 没有找到 DEEPSEEK_API_KEY。"
        "请先在当前终端设置 DeepSeek API Key。"
    )

client = OpenAI(
    api_key=_imagination_api_key,
    base_url="https://api.deepseek.com",
)

DEFAULT_MODEL = "deepseek-flash"


VALID_STATUSES = {
    "hypothesis",
    "considered",
    "planned",
    "implementing",
    "implemented",
    "tested",
    "validated",
    "failed",
    "deferred",
}


VALUE_SCORE = {
    "high": 3,
    "medium": 2,
    "low": 1,
}

FEASIBILITY_SCORE = {
    "high": 3,
    "medium": 2,
    "low": 1,
}

COMPLEXITY_SCORE = {
    "high": 3,
    "medium": 2,
    "low": 1,
}


def now():
    return datetime.now().isoformat(
        timespec="seconds"
    )


# ============================================================
# 基础存储
# ============================================================

def load_imagination_memory():
    if not os.path.exists(IMAGINATION_FILE):
        return []

    try:
        with open(
            IMAGINATION_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if not isinstance(data, list):
            return []

        return [
            normalize_existing_imagination(item)
            for item in data
            if isinstance(item, dict)
        ]

    except (
        json.JSONDecodeError,
        OSError
    ) as exc:
        print(
            f"DUOMI：读取想象记忆失败：{exc}"
        )
        return []


def save_imagination_memory(memories):
    try:
        with open(
            IMAGINATION_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                memories,
                file,
                ensure_ascii=False,
                indent=2
            )

        return True

    except OSError as exc:
        print(
            f"DUOMI：保存想象记忆失败：{exc}"
        )
        return False


# ============================================================
# 文本与想法归一化
# ============================================================

def normalize_idea(text):
    """
    用于判断两个想法是不是同一个核心想法。

    注意：
    这里只用于去重，不代表事实判断。
    """

    if not text:
        return ""

    text = str(text).lower().strip()

    # --------------------------------------------------------
    # 删除括号里的元信息
    #
    # 例如：
    # （未来假设）
    # （未来假设·再次评估）
    # (re-evaluation)
    # --------------------------------------------------------

    text = re.sub(
        r"（[^）]*）",
        "",
        text
    )

    text = re.sub(
        r"\([^)]*\)",
        "",
        text
    )

    # --------------------------------------------------------
    # 删除想法生命周期/评价类元描述
    # --------------------------------------------------------

    meta_phrases = [
        "未来假设",
        "再次评估",
        "重新评估",
        "再次想到",
        "重新思考",
        "再次思考",
        "重新考虑",
        "再次考虑",
        "重新分析",
        "第二次",
        "第三次",
        "第四次",
        "第一次",
        "第二次出现",
        "第三次出现",
    ]

    for phrase in meta_phrases:
        text = text.replace(
            phrase.lower(),
            ""
        )

    # --------------------------------------------------------
    # 去掉常见“功能描述外壳”
    # 只用于比较，不修改真正保存的 idea。
    # --------------------------------------------------------

    wrapper_words = [
        "功能",
        "模块",
        "系统",
        "机制",
        "方案",
    ]

    for word in wrapper_words:
        text = text.replace(
            word,
            ""
        )

    # --------------------------------------------------------
    # 去标点和空格
    # --------------------------------------------------------

    text = re.sub(
        r"[\s，。！？、,.!?：；;“”‘’\"'《》【】\[\]·…]",
        "",
        text
    )

    return text


def idea_similarity(a, b):
    """
    判断两个想法的文本相似度。
    """

    a = normalize_idea(a)
    b = normalize_idea(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


# ============================================================
# 数据标准化
# ============================================================

def _safe_list(value):
    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        text = str(item).strip()

        if text and text not in result:
            result.append(text)

    return result


def _safe_score(value):
    try:
        value = float(value)
    except (
        TypeError,
        ValueError
    ):
        return 0.0

    return max(
        0.0,
        min(1.0, value)
    )


def merge_unique_text_list(
    old_values,
    new_values,
    threshold=0.90
):
    """
    合并文本列表。
    对高度相似的中文描述进行去重。
    """

    if not isinstance(old_values, list):
        old_values = []

    if not isinstance(new_values, list):
        new_values = []

    result = []

    for value in old_values:
        value = str(value).strip()

        if value and value not in result:
            result.append(value)

    for value in new_values:
        value = str(value).strip()

        if not value:
            continue

        duplicated = False

        for existing in result:

            similarity = idea_similarity(
                value,
                existing
            )

            if similarity >= threshold:
                duplicated = True
                break

        if not duplicated:
            result.append(value)

    return result


def calculate_priority(
    value,
    feasibility,
    complexity,
    confidence
):
    """
    计算想法优先级。

    注意：
    复杂度越高，优先级会受到影响，
    但不会完全抵消高价值。

    返回 0~100。
    """

    value_score = VALUE_SCORE.get(
        value,
        2
    )

    feasibility_score = FEASIBILITY_SCORE.get(
        feasibility,
        2
    )

    complexity_score = COMPLEXITY_SCORE.get(
        complexity,
        2
    )

    value_part = (
        value_score / 3
    ) * 40

    feasibility_part = (
        feasibility_score / 3
    ) * 30

    complexity_part = (
        (4 - complexity_score) / 3
    ) * 20

    confidence_part = (
        _safe_score(confidence)
        * 10
    )

    score = (
        value_part
        + feasibility_part
        + complexity_part
        + confidence_part
    )

    return round(
        max(0.0, min(100.0, score)),
        1
    )


def priority_level(score):
    if score >= 75:
        return "high"

    if score >= 50:
        return "medium"

    return "low"


def normalize_existing_imagination(item):
    """
    兼容 V0.1 已经产生的旧数据。
    """

    if not item.get("created_at"):
        item["created_at"] = now()

    if not item.get("updated_at"):
        item["updated_at"] = item["created_at"]

    if item.get("status") not in VALID_STATUSES:
        item["status"] = "hypothesis"

    if not item.get("type"):
        item["type"] = "imagined_future"

    if not item.get("idea"):
        item["idea"] = "未命名想法"

    if "category" not in item:
        item["category"] = "general"

    if "source_memory_ids" not in item:
        item["source_memory_ids"] = []

    item["source_memory_ids"] = _safe_list(
        item["source_memory_ids"]
    )

    if "revisit_count" not in item:
        item["revisit_count"] = 1

    if "last_revisited_at" not in item:
        item["last_revisited_at"] = item[
            "updated_at"
        ]

    if "idea_event" not in item:
        item["idea_event"] = "new_idea"

    if "decision_history" not in item:
        item["decision_history"] = [
            {
                "event": "new_idea",
                "time": item["created_at"],
                "reason": item.get(
                    "reason",
                    ""
                )
            }
        ]

    confidence = _safe_score(
        item.get("confidence", 0.0)
    )

    item["confidence"] = confidence

    evaluation = item.get(
        "evaluation",
        {}
    )

    if not isinstance(evaluation, dict):
        evaluation = {}

    item["evaluation"] = evaluation

    value = evaluation.get(
        "value",
        "medium"
    )

    feasibility = evaluation.get(
        "feasibility",
        "medium"
    )

    complexity = evaluation.get(
        "complexity",
        "medium"
    )

    score = calculate_priority(
        value,
        feasibility,
        complexity,
        confidence
    )

    item["priority_score"] = score

    if "priority" not in item:
        item["priority"] = priority_level(
            score
        )

    if "priority_reason" not in item:
        item["priority_reason"] = (
            "根据价值、可行性、复杂度和判断信心计算。"
        )

    return item


# ============================================================
# JSON 清理
# ============================================================

def _clean_json_text(text):
    if not text:
        return ""

    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()


# ============================================================
# 模型结果标准化
# ============================================================

def normalize_imagination(data):

    if not isinstance(data, dict):
        return None

    idea = str(
        data.get("idea", "")
    ).strip()

    if not idea:
        return None

    simulation = data.get(
        "simulation",
        {}
    )

    if not isinstance(simulation, dict):
        simulation = {}

    evaluation = data.get(
        "evaluation",
        {}
    )

    if not isinstance(evaluation, dict):
        evaluation = {}

    value = str(
        evaluation.get(
            "value",
            "medium"
        )
    ).lower().strip()

    if value not in VALUE_SCORE:
        value = "medium"

    feasibility = str(
        evaluation.get(
            "feasibility",
            "medium"
        )
    ).lower().strip()

    if feasibility not in FEASIBILITY_SCORE:
        feasibility = "medium"

    complexity = str(
        evaluation.get(
            "complexity",
            "medium"
        )
    ).lower().strip()

    if complexity not in COMPLEXITY_SCORE:
        complexity = "medium"

    confidence = _safe_score(
        data.get(
            "confidence",
            0.0
        )
    )

    priority_score = calculate_priority(
        value,
        feasibility,
        complexity,
        confidence
    )

    priority = str(
        data.get(
            "priority",
            priority_level(
                priority_score
            )
        )
    ).lower().strip()

    if priority not in {
        "high",
        "medium",
        "low"
    }:
        priority = priority_level(
            priority_score
        )

    source_memory_ids = _safe_list(
        data.get(
            "source_memory_ids",
            []
        )
    )

    idea_event = str(
        data.get(
            "idea_event",
            "new_idea"
        )
    ).lower().strip()

    if idea_event not in {
        "new_idea",
        "revisit",
        "upgrade",
        "defer"
    }:
        idea_event = "new_idea"

    return {
        "type": "imagined_future",
        "status": "hypothesis",

        "created_at": now(),
        "updated_at": now(),

        "idea": idea,

        "idea_event": idea_event,

        "decision_history": [
            {
                "event": idea_event,
                "time": now(),
                "reason": str(
                    data.get(
                        "reason",
                        ""
                    )
                ).strip()
            }
        ],

        "category": str(
            data.get(
                "category",
                "general"
            )
        ).strip(),

        "reason": str(
            data.get(
                "reason",
                ""
            )
        ).strip(),

        "source_memory_ids": source_memory_ids,

        "simulation": {
            "before": str(
                simulation.get(
                    "before",
                    ""
                )
            ).strip(),

            "after": str(
                simulation.get(
                    "after",
                    ""
                )
            ).strip(),

            "new_capabilities": _safe_list(
                simulation.get(
                    "new_capabilities",
                    []
                )
            ),

            "possible_changes": _safe_list(
                simulation.get(
                    "possible_changes",
                    []
                )
            )
        },

        "dependencies": _safe_list(
            data.get(
                "dependencies",
                []
            )
        ),

        "benefits": _safe_list(
            data.get(
                "benefits",
                []
            )
        ),

        "risks": _safe_list(
            data.get(
                "risks",
                []
            )
        ),

        "evaluation": {
            "value": value,
            "feasibility": feasibility,
            "complexity": complexity,

            "recommendation": str(
                evaluation.get(
                    "recommendation",
                    "暂不确定"
                )
            ).strip(),

            "reason": str(
                evaluation.get(
                    "reason",
                    ""
                )
            ).strip()
        },

        "priority": priority,
        "priority_score": priority_score,

        "priority_reason": str(
            data.get(
                "priority_reason",
                ""
            )
        ).strip(),

        "confidence": confidence,

        "revisit_count": 1,
        "last_revisited_at": now()
    }


# ============================================================
# Prompt
# ============================================================

def _build_prompt(
    user_input,
    memories,
    learning_context="",
    current_capabilities=None,
    imagination_history=None
):

    if current_capabilities is None:
        current_capabilities = []

    if imagination_history is None:
        imagination_history = []

    memory_text = json.dumps(
        memories,
        ensure_ascii=False,
        indent=2
    )

    imagination_text = json.dumps(
        imagination_history,
        ensure_ascii=False,
        indent=2
    )

    return f"""
你是 DUOMI 的智能联想与未来想象系统。

你正在帮助一个正在成长的具身智能机器人思考未来。

==================================================
核心任务
==================================================

根据：

1. 当前真实能力
2. 长期记忆
3. 用户长期目标
4. 学习规律
5. 已经产生过的想法

提出一个值得认真考虑的新功能，
并模拟它实现后的结果，
然后自己进行工程评价。

==================================================
非常重要
==================================================

你提出的一切都属于【未来假设】。

绝对不能把尚未实现的功能说成事实。

例如：

错误：
“DUOMI 已经可以飞行。”

正确：
“如果未来增加可收纳飞行模块，
DUOMI 可能获得飞行能力。”

==================================================
关于已有想法
==================================================

下面是 DUOMI 过去已经想到的功能：

{imagination_text}

如果当前问题明确指定了一个功能，
必须优先分析该功能。

不要为了“看起来有新意”而
故意换成完全不同的功能。

如果你发现这个想法以前已经出现过：

1. 不要创建重复的核心想法。
2. 将其视为 revisit。
3. 说明这次为什么再次想到它。
4. 比较以前评价和现在评价。
5. 如果价值、可行性、复杂度或优先级发生明显变化，
   可以标记为 upgrade。
6. 如果重新评估后应该暂时停止考虑，
   可以标记为 defer。

==================================================
联想方式
==================================================

优先考虑：

- 当前能力的自然延伸
- 两个现有能力组合
- 发现的能力缺口
- 用户长期目标
- 机器人身体未来发展
- 已经出现但尚未实现的想法

==================================================
当前真实能力
==================================================

{json.dumps(
    current_capabilities,
    ensure_ascii=False,
    indent=2
)}

==================================================
长期记忆
==================================================

{memory_text}

==================================================
学习规律
==================================================

{learning_context}

==================================================
当前上下文
==================================================

{user_input}

==================================================
输出要求
==================================================

只返回合法 JSON。

格式：

{{
  "idea": "功能名称",

  "category": "body / perception / speech / memory / autonomy / communication / safety / other",

  "reason": "为什么想到它",

  "source_memory_ids": [
    "可能影响这个联想的长期记忆ID"
  ],

  "simulation": {{
    "before": "加入前的状态",
    "after": "加入后的假设状态",
    "new_capabilities": [
      "新增能力"
    ],
    "possible_changes": [
      "可能变化"
    ]
  }},

  "dependencies": [
    "工程依赖"
  ],

  "benefits": [
    "收益"
  ],

  "risks": [
    "风险"
  ],

  "evaluation": {{
    "value": "high / medium / low",
    "feasibility": "high / medium / low",
    "complexity": "high / medium / low",
    "recommendation": "建议 / 暂缓 / 不建议",
    "reason": "评价理由"
  }},

  "priority": "high / medium / low",

  "priority_reason": "为什么这个想法具有这个优先级",

  "idea_event": "new_idea / revisit / upgrade / defer",

  "confidence": 0.0
}}

其中：

new_idea：
以前没有出现过这个核心想法。

revisit：
以前已经想到过，现在重新思考。

upgrade：
以前已经想到过，但这次发现价值、可行性、
优先级或实现路径发生了明显改善。

defer：
重新评估后，认为暂时应该放下或延后。

==================================================
评价原则
==================================================

高价值不等于现在应该做。

例如：

价值 high
可行性 low
复杂度 high

完全可以得出：

“长期值得考虑，但目前暂缓。”

不要为了鼓励用户而无条件评价为建议。
"""


# ============================================================
# 想法合并
# ============================================================

def merge_imagination(existing_memories, new_item):
    """
    合并一次新的智能联想。

    生命周期：
    new_idea -> 新想法
    revisit  -> 已有想法，核心判断无实质变化
    upgrade  -> 核心评价/优先级/信心发生实质变化
    defer    -> 从非暂缓状态转为明确暂缓

    LLM 的 idea_event 只是候选值。
    最终事件由程序根据前后状态计算。
    """

    def _as_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _text(value):
        return str(value).strip() if value is not None else ""

    def _semantic_dedupe(items, threshold=0.84, max_items=8):
        """
        专门用于 benefits / risks / dependencies 的中文短句去重。

        规则：
        1. 完全相同 -> 去重
        2. 删除常见虚词、标点后高度相似 -> 去重
        3. 二元字符片段高度重合 -> 去重
        4. 保留前面的描述，避免反复复评导致列表无限增长
        """

        stop_words = {
            "可能",
            "可以",
            "能够",
            "会",
            "将",
            "并",
            "并且",
            "以及",
            "还有",
            "通过",
            "从而",
            "因此",
            "进一步",
            "长期上",
            "作为",
            "用于",
            "实现",
            "形成",
            "获得",
            "加入后",
            "未来",
            "自然",
            "直接",
            "更加",
            "更强",
        }

        def normalize(value):
            if value is None:
                return ""

            value = str(value).strip().lower()

            # 去标点、空格
            value = re.sub(
                r"[\s，。！？、；：:,.!?（）()【】\[\]“”\"‘’'·\-—_]+",
                "",
                value
            )

            # 删除常见虚词
            changed = True

            while changed:
                changed = False

                for word in sorted(
                    stop_words,
                    key=len,
                    reverse=True
                ):
                    new_value = value.replace(
                        word,
                        ""
                    )

                    if new_value != value:
                        value = new_value
                        changed = True

            return value

        def bigrams(value):
            if len(value) < 2:
                return {value} if value else set()

            return {
                value[i:i + 2]
                for i in range(len(value) - 1)
            }

        def similarity(a, b):
            if a == b:
                return 1.0

            if not a or not b:
                return 0.0

            sequence = SequenceMatcher(
                None,
                a,
                b
            ).ratio()

            set_a = bigrams(a)
            set_b = bigrams(b)

            if not set_a or not set_b:
                jaccard = 0.0
            else:
                jaccard = len(
                    set_a & set_b
                ) / len(
                    set_a | set_b
                )

            # 两种相似度取较高者
            return max(
                sequence,
                jaccard
            )

        result = []

        for raw in items or []:
            value = str(raw).strip()

            if not value:
                continue

            normalized = normalize(value)

            if not normalized:
                continue

            duplicate = False

            for old in result:
                old_normalized = normalize(old)

                score = similarity(
                    normalized,
                    old_normalized
                )

                if score >= threshold:
                    duplicate = True
                    break

            if not duplicate:
                result.append(value)

            if len(result) >= max_items:
                break

        return result


    def _evaluation_core(evaluation):
        evaluation = evaluation or {}

        return {
            "value": _text(evaluation.get("value")),
            "feasibility": _text(evaluation.get("feasibility")),
            "complexity": _text(evaluation.get("complexity")),
            "recommendation": _text(
                evaluation.get("recommendation")
            ),
        }

    def _is_defer(value):
        value = _text(value).lower()

        words = (
            "暂缓",
            "不建议",
            "暂不",
            "先不",
            "延期",
            "推迟",
            "defer",
        )

        return any(word in value for word in words)

    # -----------------------------------------------------
    # 1. 找最相似想法
    # -----------------------------------------------------
    best_index = None
    best_similarity = 0.0

    new_idea = _text(new_item.get("idea"))

    for i, old_item in enumerate(existing_memories):
        old_idea = _text(old_item.get("idea"))

        if not new_idea or not old_idea:
            continue

        try:
            similarity = idea_similarity(
                new_idea,
                old_idea
            )
        except Exception:
            similarity = 1.0 if new_idea == old_idea else 0.0

        if similarity > best_similarity:
            best_similarity = similarity
            best_index = i

    # -----------------------------------------------------
    # 2. 新想法
    # -----------------------------------------------------
    if best_index is None or best_similarity < 0.72:

        item = deepcopy(new_item)
        timestamp = now()

        item["idea_event"] = "new_idea"
        item["revisit_count"] = 1
        item["updated_at"] = timestamp

        if not item.get("created_at"):
            item["created_at"] = timestamp

        item["source_memory_ids"] = list(
            dict.fromkeys(
                item.get("source_memory_ids", [])
            )
        )[:3]

        item["benefits"] = _semantic_dedupe(
            item.get("benefits", [])
        )

        item["risks"] = _semantic_dedupe(
            item.get("risks", [])
        )

        item["dependencies"] = _semantic_dedupe(
            item.get("dependencies", [])
        )

        item["decision_history"] = [{
            "timestamp": timestamp,
            "event": "new_idea",
            "previous_priority": None,
            "new_priority": item.get(
                "priority_score"
            ),
            "previous_evaluation": None,
            "new_evaluation": _evaluation_core(
                item.get("evaluation")
            ),
            "reason": item.get("reason", ""),
        }]

        existing_memories.append(item)

        return item

    # -----------------------------------------------------
    # 3. 已存在 -> 重新思考
    # -----------------------------------------------------
    existing = existing_memories[best_index]

    timestamp = now()

    previous_priority = _as_float(
        existing.get("priority_score"),
        0.0
    )

    new_priority = _as_float(
        new_item.get("priority_score"),
        previous_priority
    )

    previous_confidence = _as_float(
        existing.get("confidence"),
        0.0
    )

    new_confidence = _as_float(
        new_item.get("confidence"),
        previous_confidence
    )

    previous_eval = _evaluation_core(
        existing.get("evaluation")
    )

    new_eval = _evaluation_core(
        new_item.get("evaluation")
    )

    # -----------------------------------------------------
    # 4. 判断是否发生实质变化
    # -----------------------------------------------------
    priority_changed = (
        abs(
            new_priority
            - previous_priority
        ) >= 5.0
    )

    evaluation_changed = (
        previous_eval != new_eval
    )

    confidence_changed = (
        abs(
            new_confidence
            - previous_confidence
        ) >= 0.10
    )

    previous_recommendation = (
        previous_eval.get("recommendation")
    )

    new_recommendation = (
        new_eval.get("recommendation")
    )

    previous_defer = _is_defer(
        previous_recommendation
    )

    new_defer = _is_defer(
        new_recommendation
    )

    # -----------------------------------------------------
    # 5. 程序最终决定生命周期事件
    # -----------------------------------------------------
    if new_defer and not previous_defer:
        final_event = "defer"

    elif (
        priority_changed
        or evaluation_changed
        or confidence_changed
    ):
        final_event = "upgrade"

    else:
        final_event = "revisit"

    # -----------------------------------------------------
    # 6. 更新核心字段
    # -----------------------------------------------------
    existing["updated_at"] = timestamp

    existing["revisit_count"] = int(
        existing.get("revisit_count", 0)
    ) + 1

    if new_item.get("category"):
        existing["category"] = (
            new_item["category"]
        )

    if new_item.get("status"):
        existing["status"] = (
            new_item["status"]
        )

    if new_item.get("evaluation"):
        existing["evaluation"] = deepcopy(
            new_item["evaluation"]
        )

    if "priority" in new_item:
        existing["priority"] = (
            new_item.get("priority")
        )

    if "priority_score" in new_item:
        existing["priority_score"] = (
            new_item.get("priority_score")
        )

    if "confidence" in new_item:
        existing["confidence"] = (
            new_item.get("confidence")
        )

    # 最新思考理由
    if new_item.get("reason"):
        existing["reason"] = (
            new_item["reason"]
        )

    # -----------------------------------------------------
    # 7. 合并并去重
    # -----------------------------------------------------
    for field in (
        "benefits",
        "risks",
        "dependencies",
    ):
        existing[field] = _semantic_dedupe(
            list(existing.get(field, []))
            + list(new_item.get(field, []))
        )

    # -----------------------------------------------------
    # 8. 来源记忆最多 3 条
    # -----------------------------------------------------
    source_ids = []

    for source_id in (
        list(existing.get(
            "source_memory_ids", []
        ))
        +
        list(new_item.get(
            "source_memory_ids", []
        ))
    ):
        if (
            source_id
            and source_id not in source_ids
        ):
            source_ids.append(source_id)

    existing["source_memory_ids"] = (
        source_ids[:3]
    )

    # -----------------------------------------------------
    # 9. 决策历史
    # -----------------------------------------------------
    history = existing.setdefault(
        "decision_history",
        []
    )

    history.append({
        "timestamp": timestamp,
        "event": final_event,
        "previous_priority": round(
            previous_priority,
            2
        ),
        "new_priority": round(
            new_priority,
            2
        ),
        "previous_evaluation": previous_eval,
        "new_evaluation": new_eval,
        "reason": new_item.get(
            "reason",
            ""
        ),
    })

    existing["idea_event"] = final_event

    return existing


def generate_imagination(
    user_input="",
    memory_context=None,
    save_result=True,
    model=None,
    **kwargs
):
    """
    生成一次智能联想，并可合并到 imagination_memory.json。

    LLM 负责提出和分析假设；
    merge_imagination() 负责最终生命周期事件判断。
    """

    import inspect

    if not user_input:
        user_input = (
            kwargs.get("query")
            or kwargs.get("user_request")
            or kwargs.get("input_text")
            or "请基于 DUOMI 当前能力和长期目标，提出一个值得考虑的未来功能。"
        )

    if memory_context is None:
        memory_context = (
            kwargs.get("memories")
            or kwargs.get("memory_context")
        )

    if memory_context is None:
        try:
            memory_context = load_important_memory()
        except Exception:
            memory_context = []

    history = load_imagination_memory()
    selected_model = model or kwargs.get("model") or DEFAULT_MODEL

    try:
        signature = inspect.signature(_build_prompt)
        params = list(signature.parameters.values())
        args = []

        for param in params:
            name = param.name.lower()

            if name in {
                "user_input",
                "query",
                "request",
                "user_request",
                "input_text",
            }:
                args.append(user_input)

            elif name in {
                "memory_context",
                "memories",
                "memory",
                "context",
            }:
                args.append(memory_context)

            elif name in {
                "imagination_history",
                "history",
                "existing_memories",
                "existing_history",
            }:
                args.append(history)

            elif param.default is inspect.Parameter.empty:
                raise TypeError(
                    f"无法识别 _build_prompt() 参数：{param.name}"
                )

        prompt = _build_prompt(*args)

    except Exception as exc:
        raise RuntimeError(
            f"_build_prompt() 调用失败：{exc}"
        ) from exc

    response = client.chat.completions.create(
        model=selected_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是 DUOMI 的智能联想模块。"
                    "你的输出只能描述未来假设，不得把假设当成已经实现的事实。"
                    "请严格输出 JSON。"
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.7,
    )

    raw = response.choices[0].message.content
    cleaned = _clean_json_text(raw)

    try:
        parsed = json.loads(cleaned)
    except Exception as exc:
        raise ValueError(
            f"智能联想模型没有返回合法 JSON：{exc}\n"
            f"原始内容：{raw}"
        ) from exc

    if isinstance(parsed, dict):
        if isinstance(parsed.get("result"), dict):
            parsed = parsed["result"]
        elif isinstance(parsed.get("imagination"), dict):
            parsed = parsed["imagination"]
        elif isinstance(parsed.get("data"), dict):
            parsed = parsed["data"]

    if not isinstance(parsed, dict):
        raise ValueError("智能联想结果必须是 JSON 对象")

    item = normalize_imagination(parsed)

    try:
        important = load_important_memory()
        valid_ids = set()

        if isinstance(important, list):
            for memory in important:
                if isinstance(memory, dict):
                    memory_id = memory.get("id")
                    if memory_id:
                        valid_ids.add(memory_id)

        elif isinstance(important, dict):
            for key, memory in important.items():
                if key:
                    valid_ids.add(key)

                if isinstance(memory, dict):
                    memory_id = memory.get("id")
                    if memory_id:
                        valid_ids.add(memory_id)

        candidate_sources = item.get(
            "source_memory_ids",
            []
        )

        filtered_sources = []

        for source_id in candidate_sources:
            if (
                source_id
                and source_id in valid_ids
                and source_id not in filtered_sources
            ):
                filtered_sources.append(source_id)

        item["source_memory_ids"] = filtered_sources[:3]

    except Exception:
        item["source_memory_ids"] = list(
            dict.fromkeys(
                item.get("source_memory_ids", [])
            )
        )[:3]

    if save_result:
        result = merge_imagination(
            history,
            item
        )

        save_imagination_memory(history)

        event = result.get(
            "idea_event",
            "revisit"
        )

        revisit_count = int(
            result.get(
                "revisit_count",
                1
            )
        )

        if event == "new_idea":
            print("DUOMI：产生了一个新的未来想法")
        else:
            print(
                "DUOMI：发现相似想法，本次作为"
                f"第 {revisit_count} 次重新思考"
            )

        return result

    return item


def get_top_imagination(
    limit=5
):
    memories = load_imagination_memory()

    memories.sort(
        key=lambda item: (
            item.get(
                "priority_score",
                0
            ),
            item.get(
                "confidence",
                0
            ),
            item.get(
                "revisit_count",
                0
            )
        ),
        reverse=True
    )

    return memories[:limit]


def update_imagination_status(
    imagination_id,
    status
):
    """
    手动推进一个想法的生命周期。

    目前只允许显式调用，
    不允许模型自己把 hypothesis
    自动变成 implemented。
    """

    if status not in VALID_STATUSES:
        return False

    memories = load_imagination_memory()

    for item in memories:

        if item.get("id") == imagination_id:

            item["status"] = status
            item["updated_at"] = now()

            save_imagination_memory(
                memories
            )

            return True

    return False


# ============================================================
# 格式化显示
# ============================================================

def format_imagination(
    imagination
):

    if not imagination:
        return (
            "DUOMI：这次没有形成有效联想。"
        )

    evaluation = imagination.get(
        "evaluation",
        {}
    )

    simulation = imagination.get(
        "simulation",
        {}
    )

    lines = [
        "",
        "==============================",
        "DUOMI 智能联想",
        "==============================",
        "",
        f"我想到的功能："
        f"{imagination.get('idea', '')}",

        f"类型："
        f"{imagination.get('category', '')}",

        f"状态："
        f"{imagination.get('status', '')}",

        f"本次事件："
        f"{imagination.get('idea_event', '')}",

        f"优先级："
        f"{imagination.get('priority', '')}"
        f"（{imagination.get('priority_score', 0)}）",

        f"这是我第 "
        f"{imagination.get('revisit_count', 1)}"
        f" 次想到这个想法",

        "",
        f"为什么想到："
        f"{imagination.get('reason', '')}",

        "",
        "如果真的加入：",
        f"加入前："
        f"{simulation.get('before', '')}",

        f"加入后："
        f"{simulation.get('after', '')}",

        "",
        "可能新增能力：",
    ]

    for item in simulation.get(
        "new_capabilities",
        []
    ):
        lines.append(
            f"  · {item}"
        )

    lines.extend([
        "",
        "可能收益：",
    ])

    for item in imagination.get(
        "benefits",
        []
    ):
        lines.append(
            f"  · {item}"
        )

    lines.extend([
        "",
        "潜在风险：",
    ])

    for item in imagination.get(
        "risks",
        []
    ):
        lines.append(
            f"  · {item}"
        )

    lines.extend([
        "",
        "工程依赖：",
    ])

    for item in imagination.get(
        "dependencies",
        []
    ):
        lines.append(
            f"  · {item}"
        )

    lines.extend([
        "",
        "我的评价：",
        f"价值："
        f"{evaluation.get('value', '')}",

        f"可行性："
        f"{evaluation.get('feasibility', '')}",

        f"复杂度："
        f"{evaluation.get('complexity', '')}",

        f"建议："
        f"{evaluation.get('recommendation', '')}",

        f"理由："
        f"{evaluation.get('reason', '')}",

        "",
        f"优先级理由："
        f"{imagination.get('priority_reason', '')}",

        "",
        f"来源记忆："
        f"{', '.join(imagination.get('source_memory_ids', [])) or '无'}",

        f"信心："
        f"{imagination.get('confidence', 0):.2f}",

        "",
        "这是我的未来假设，不是已经实现的能力。",
        "==============================",
    ])

    return "\n".join(lines)


# ============================================================
# 独立测试入口
# ============================================================

if __name__ == "__main__":

    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ.get(
            "DEEPSEEK_API_KEY"
        ),
        base_url="https://api.deepseek.com"
    )

    try:
        with open(
            "important_memory.json",
            "r",
            encoding="utf-8"
        ) as file:
            memories = json.load(file)

    except (
        json.JSONDecodeError,
        OSError
    ):
        memories = []

    current_capabilities = [
        "长期记忆",
        "TTS 语音输出",
        "联网",
        "基础情绪状态",
        "学习系统",
        "反思系统",
    ]

    question = (
        "如果未来希望让 DUOMI 获得一种"
        "可收纳的飞行能力，"
        "请认真思考这个想法是否值得开发。"
    )

    result = generate_imagination(
        client=client,
        user_input=question,
        memories=memories,
        learning_context="",
        current_capabilities=current_capabilities,
        model=DEFAULT_MODEL,
        save_result=True
    )

    print(
        format_imagination(result)
    )
