import json
import os
import re
from openai import OpenAI

from imagination_system import (
    DEFAULT_MODEL,
    _clean_json_text,
    load_imagination_memory,
    generate_imagination,
)

from memory_manager import load_important_memory


# 加载 DUOMI 项目的环境变量
_api_key = os.environ.get("DEEPSEEK_API_KEY")

if not _api_key:
    raise RuntimeError(
        "❌ 没有找到 DEEPSEEK_API_KEY。"
        "请先在当前终端设置 DeepSeek API Key。"
    )

# DUOMI 联想触发器自己的模型客户端
client = OpenAI(
    api_key=_api_key,
    base_url="https://api.deepseek.com",
)


# =========================================================
# V0.4.0 自主联想触发器
# =========================================================

OBVIOUS_SMALL_TALK = {
    "你好",
    "嗨",
    "嘿",
    "早上好",
    "早安",
    "晚上好",
    "晚安",
    "谢谢",
    "谢谢你",
    "好的",
    "好",
    "嗯",
    "哦",
    "哈哈",
    "拜拜",
    "再见",
}


def _is_obvious_small_talk(text):
    text = str(text or "").strip()

    if not text:
        return True

    if text in OBVIOUS_SMALL_TALK:
        return True

    if len(text) <= 2 and not any(
        char in text
        for char in "？?！!"
    ):
        return True

    return False


def _safe_bool(value, default=False):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    text = str(value or "").strip().lower()

    if text in {
        "true",
        "yes",
        "1",
        "是",
        "值得",
        "需要",
        "应该",
    }:
        return True

    if text in {
        "false",
        "no",
        "0",
        "否",
        "不值得",
        "不需要",
        "不应该",
    }:
        return False

    return default


def _safe_float(value, default=0.0):
    try:
        value = float(value)
        return max(0.0, min(1.0, value))
    except (TypeError, ValueError):
        return default


def _memory_summary(memories, max_items=12):
    result = []

    if not isinstance(memories, list):
        return result

    for memory in memories[:max_items]:
        if not isinstance(memory, dict):
            continue

        result.append({
            "id": memory.get("id"),
            "type": memory.get("type"),
            "content": memory.get("content"),
            "importance": memory.get("importance"),
        })

    return result


def _imagination_summary(history, max_items=12):
    result = []

    if not isinstance(history, list):
        return result

    # 优先高优先级
    items = sorted(
        history,
        key=lambda item: float(
            item.get("priority_score", 0) or 0
        ),
        reverse=True,
    )

    for item in items[:max_items]:
        if not isinstance(item, dict):
            continue

        result.append({
            "idea": item.get("idea"),
            "category": item.get("category"),
            "status": item.get("status"),
            "idea_event": item.get("idea_event"),
            "priority": item.get("priority"),
            "priority_score": item.get("priority_score"),
            "revisit_count": item.get("revisit_count"),
        })

    return result


def _build_trigger_prompt(
    user_input,
    memories,
    imagination_history,
):
    memory_text = json.dumps(
        _memory_summary(memories),
        ensure_ascii=False,
        indent=2,
    )

    imagination_text = json.dumps(
        _imagination_summary(imagination_history),
        ensure_ascii=False,
        indent=2,
    )

    return f"""
你现在是 DUOMI 的“自主联想触发判断器”。

你的任务不是直接提出功能，而是判断：
“刚才这句话，是否值得让我进一步进行一次未来联想？”

DUOMI 的目标：
- 从零开始，一起进步
- 不只是聊天和陪伴
- 逐渐具备记忆、学习、观察、判断和现实行动能力

重要原则：

1. 普通闲聊、简单问答、事实查询、天气、价格、翻译、计算等，
   通常不值得启动智能联想。

2. 如果用户表达了：
   - 新目标
   - 新需求
   - 新功能
   - 改造设想
   - 多个已有能力的组合可能
   - 当前问题可以通过未来能力解决
   - 某个长期目标的新方向
   - 对 DUOMI 未来行为的设想
   则可能值得启动联想。

3. 不能因为“出现了 DUOMI”三个字就自动触发。

4. 不要把用户的一句话直接当成事实。

5. 已经存在的想法，如果用户又提到，
   可以建议“重新思考”，而不是强行创建新想法。

6. 只有真正有潜在长期价值的内容才值得联想。

7. 联想只是未来假设，不代表 DUOMI 已经拥有该能力。

当前用户输入：
{user_input}

当前重要记忆：
{memory_text}

当前已经存在的未来想法：
{imagination_text}

请严格输出 JSON，不要输出 Markdown。

JSON 格式必须是：

{{
  "should_imagine": true,
  "confidence": 0.0,
  "trigger_type": "new_capability",
  "focus": "值得进一步思考的方向",
  "reason": "为什么值得联想",
  "internal_or_surface": "internal"
}}

trigger_type 只能是：

- new_capability
- capability_combination
- problem_solution
- long_term_goal
- repeated_pattern
- revisit
- none

internal_or_surface 只能是：

- internal
- surface
- undecided

注意：
internal_or_surface 只是候选意见。
最终是否告诉用户，由程序结合想法优先级、变化程度和置信度决定。

如果不值得联想：

{{
  "should_imagine": false,
  "confidence": 0.95,
  "trigger_type": "none",
  "focus": "",
  "reason": "这是普通对话，不需要启动未来联想",
  "internal_or_surface": "internal"
}}
"""


def judge_imagination_trigger(
    user_input,
    memories=None,
    imagination_history=None,
    model=None,
):
    """
    判断当前用户输入是否值得触发智能联想。

    不修改任何记忆。
    """

    user_input = str(user_input or "").strip()

    if _is_obvious_small_talk(user_input):
        return {
            "should_imagine": False,
            "confidence": 1.0,
            "trigger_type": "none",
            "focus": "",
            "reason": "普通闲聊，无需启动智能联想。",
            "internal_or_surface": "internal",
        }

    if memories is None:
        try:
            memories = load_important_memory()
        except Exception:
            memories = []

    if imagination_history is None:
        try:
            imagination_history = load_imagination_memory()
        except Exception:
            imagination_history = []

    prompt = _build_trigger_prompt(
        user_input,
        memories,
        imagination_history,
    )

    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是 DUOMI 的自主联想触发判断器。"
                    "只负责判断是否值得联想。"
                    "必须严格输出 JSON。"
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content
    cleaned = _clean_json_text(raw)

    try:
        result = json.loads(cleaned)
    except Exception:
        return {
            "should_imagine": False,
            "confidence": 0.0,
            "trigger_type": "none",
            "focus": "",
            "reason": "触发判断模型返回的数据无法解析。",
            "internal_or_surface": "internal",
        }

    if not isinstance(result, dict):
        return {
            "should_imagine": False,
            "confidence": 0.0,
            "trigger_type": "none",
            "focus": "",
            "reason": "触发判断结果格式错误。",
            "internal_or_surface": "internal",
        }

    result["should_imagine"] = _safe_bool(
        result.get("should_imagine"),
        False,
    )

    result["confidence"] = _safe_float(
        result.get("confidence"),
        0.0,
    )

    result["trigger_type"] = str(
        result.get("trigger_type")
        or "none"
    ).strip()

    result["focus"] = str(
        result.get("focus")
        or ""
    ).strip()

    result["reason"] = str(
        result.get("reason")
        or ""
    ).strip()

    result["internal_or_surface"] = str(
        result.get("internal_or_surface")
        or "internal"
    ).strip()

    return result


def _should_surface_imagination(item):
    """
    决定已经产生的想法是否值得告诉用户。

    规则：
    - new_idea：有一定优先级和信心才告诉
    - upgrade：原则上告诉
    - revisit：没有实质变化时不打扰用户
    - defer：只有第一次从可推进状态变成暂缓时才考虑告诉
    """

    event = str(
        item.get("idea_event")
        or ""
    ).strip()

    priority_score = _safe_float(
        float(item.get("priority_score", 0) or 0) / 100
    )

    confidence = _safe_float(
        item.get("confidence"),
        0.0,
    )

    if event == "upgrade":
        return True

    if event == "new_idea":
        return (
            priority_score >= 0.70
            and confidence >= 0.65
        )

    if event == "defer":
        return confidence >= 0.75

    # revisit 默认留在内部
    return False


def _build_surface_message(item):
    """
    将内部联想压缩成自然的一句话/短段落。
    """

    idea = str(
        item.get("idea")
        or "一个未来功能"
    ).strip()

    evaluation = item.get(
        "evaluation",
        {}
    ) or {}

    value = str(
        evaluation.get("value")
        or ""
    ).strip()

    feasibility = str(
        evaluation.get("feasibility")
        or ""
    ).strip()

    recommendation = str(
        evaluation.get("recommendation")
        or ""
    ).strip()

    reason = str(
        evaluation.get("reason")
        or item.get("priority_reason")
        or item.get("reason")
        or ""
    ).strip()

    message = (
        f"Deng，我刚才突然联想到一个未来可能对我有用的功能："
        f"{idea}。"
    )

    if value:
        message += f"我目前判断它的潜在价值是{value}"

    if feasibility:
        message += f"，可行性暂时是{feasibility}"

    if recommendation:
        message += f"，现在的建议是“{recommendation}”"

    if reason:
        # 控制表面输出长度，详细内容仍保存在想象记忆里
        reason = re.sub(
            r"\s+",
            " ",
            reason,
        )

        if len(reason) > 120:
            reason = reason[:120] + "……"

        message += f"。主要原因是：{reason}"

    return message


def auto_imagine(
    user_input,
    memories=None,
    imagination_history=None,
    save_result=True,
    model=None,
):
    """
    V0.4 核心流程：

    用户输入
        ↓
    触发判断
        ↓
    值得联想？
       / \
     否   是
     ↓     ↓
    返回   generate_imagination()
             ↓
       生命周期判断
             ↓
       是否值得告诉用户
    """

    trigger = judge_imagination_trigger(
        user_input=user_input,
        memories=memories,
        imagination_history=imagination_history,
        model=model,
    )

    result = {
        "trigger": trigger,
        "imagined": False,
        "surface": False,
        "message": "",
        "imagination": None,
    }

    if not trigger.get("should_imagine"):
        result["decision"] = "NO_IMAGINATION"
        return result

    focus = trigger.get("focus", "").strip()

    imagination_input = str(
        user_input
    ).strip()

    if focus:
        imagination_input += (
            "\n\n"
            "[内部联想关注方向]\n"
            + focus
        )

    imagination = generate_imagination(
        user_input=imagination_input,
        memory_context=memories,
        save_result=save_result,
        model=model,
    )

    result["imagined"] = True
    result["imagination"] = imagination

    should_surface = _should_surface_imagination(
        imagination
    )

    result["surface"] = should_surface

    if should_surface:
        result["decision"] = (
            "IMAGINE_AND_SURFACE"
        )
        result["message"] = _build_surface_message(
            imagination
        )
    else:
        result["decision"] = (
            "IMAGINE_INTERNAL"
        )

    return result


# =========================================================
# 独立测试
# =========================================================

if __name__ == "__main__":

    test_inputs = [
        "你好",
        "今天下雨了吗",
        "我想让多米以后能自己去厨房看看有没有忘记关火",
        "以后多米能不能同时用摄像头和记忆理解我家里的空间",
        "我最近在想，要不要给多米加一个麦克风",
    ]

    print("=" * 70)
    print("DUOMI Imagination Trigger V0.4.0")
    print("=" * 70)

    for text in test_inputs:

        print()
        print("用户：", text)

        result = auto_imagine(
            user_input=text,
            save_result=False,
        )

        trigger = result["trigger"]

        print(
            "是否联想：",
            trigger.get("should_imagine")
        )

        print(
            "触发类型：",
            trigger.get("trigger_type")
        )

        print(
            "置信度：",
            trigger.get("confidence")
        )

        print(
            "原因：",
            trigger.get("reason")
        )

        print(
            "最终决策：",
            result.get("decision")
        )

        if result.get("imagination"):
            imagination = result["imagination"]

            print(
                "联想结果：",
                imagination.get("idea")
            )

            print(
                "事件：",
                imagination.get("idea_event")
            )

            print(
                "优先级：",
                imagination.get("priority"),
                imagination.get("priority_score")
            )

        if result.get("message"):
            print(
                "对用户说：",
                result["message"]
            )

    print()
    print("=" * 70)
