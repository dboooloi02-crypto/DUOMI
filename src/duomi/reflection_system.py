import json

from learning_system import get_learning_patterns


def _parse_json(text):
    """
    尽可能从模型输出中提取 JSON 对象。
    """
    if not text:
        return None

    text = text.strip()

    # 去掉 markdown code fence
    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取第一个 JSON 对象
    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


def reflect_on_turn(
    client,
    user_input,
    answer,
    event_type=None,
    emotion_before=None,
    emotion_after=None,
):
    """
    让 DUOMI 对一轮真实经历进行反思。

    注意：
    这里不是让模型修改自己，而是让模型提炼“经验候选”。
    真正进入 learned_rules.json 仍然需要经过证据累计。
    """

    learning_patterns = get_learning_patterns()

    prompt = f"""
你是 DUOMI 的自主反思模块。

请分析刚刚发生的一轮真实交互，判断 DUOMI 是否从这次经历中获得了
值得以后参考的行为经验。

用户输入：
{user_input}

DUOMI 回答：
{answer}

事件类型：
{event_type}

DUOMI 已有学习模式：
{json.dumps(learning_patterns, ensure_ascii=False, indent=2)}

请优先判断这次经历是否属于已有 pattern_key。
如果属于同一个行为模式，请复用已有的 pattern_key，
不要因为措辞不同就创造新的 pattern_key。

只有确实出现新的行为模式时，才创建新的 pattern_key。

pattern_key 必须：
- 使用简短英文小写
- 单词之间使用下划线
- 描述行为模式，而不是描述具体一句话
- 例如：vague_negative_feedback

情绪变化前：
{json.dumps(emotion_before, ensure_ascii=False)}

情绪变化后：
{json.dumps(emotion_after, ensure_ascii=False)}

你的任务：

1. 判断这次经历是否真的产生了值得学习的经验。
2. 不要因为普通闲聊就强行制造经验。
3. 不要把一次偶然事件直接当成永久规律。
4. 学习内容应该描述“以后如何处理类似情况”。
5. 不要学习没有证据支持的用户信息。
6. 不要把事实、观点和猜测混在一起。
7. confidence 表示你对这个学习候选的信心，而不是事实真值。
8. rule 必须是可执行的行为规律。
9. 如果没有值得学习的内容，should_learn 必须为 false。

只返回 JSON，不要添加解释：

{{
  "should_learn": true,
  "pattern_key": "vague_negative_feedback",
  "lesson": "这次经历让我认识到……",
  "rule": "以后遇到类似情况时，应当……",
  "confidence": 0.72,
  "reason": "为什么这次经历值得记录"
}}

或者：

{{
  "should_learn": false,
  "lesson": "",
  "rule": "",
  "confidence": 0.0,
  "reason": "这次只是普通闲聊，没有稳定的学习价值"
}}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=[
                {
                    "role": "system",
                    "content": "你是 DUOMI 的自主反思模块，只输出合法 JSON。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response.choices[0].message.content
        result = _parse_json(content)

        if not isinstance(result, dict):
            return None

        should_learn = result.get("should_learn", False)

        if not isinstance(should_learn, bool):
            should_learn = False

        result["should_learn"] = should_learn

        result["pattern_key"] = str(
            result.get("pattern_key", "")
        ).strip().lower()

        result["lesson"] = str(
            result.get("lesson", "")
        ).strip()

        result["rule"] = str(
            result.get("rule", "")
        ).strip()

        result["reason"] = str(
            result.get("reason", "")
        ).strip()

        try:
            result["confidence"] = float(
                result.get("confidence", 0.0)
            )
        except (TypeError, ValueError):
            result["confidence"] = 0.0

        result["confidence"] = max(
            0.0,
            min(1.0, result["confidence"])
        )

        if not result["should_learn"]:
            return result

        if not result["lesson"] or not result["rule"]:
            result["should_learn"] = False

        return result

    except Exception:
        # 反思失败不能影响 DUOMI 正常聊天。
        return None
