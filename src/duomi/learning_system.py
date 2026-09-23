import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

LEARNING_HISTORY_FILE = BASE_DIR / "learning_history.jsonl"
LEARNED_RULES_FILE = BASE_DIR / "learned_rules.json"


# 一个经验至少被重复观察几次，才允许升级成“主动规则”。
RULE_ACTIVATION_COUNT = 3


LEARNING_TEMPLATES = {
    "praise": {
        "lesson": "当前行为获得了用户明确的正向反馈，可以继续保持类似的处理方式。",
        "rule": "保留获得用户明确肯定的有效行为。",
    },
    "criticism": {
        "lesson": "用户对当前表现提出了负面反馈。下次应先确认具体问题，再调整行为，不要过早猜测原因。",
        "rule": "收到负面反馈后，优先确认具体问题，再决定如何修改。",
    },
    "discovery": {
        "lesson": "用户出现新的发现或未知信息时，应保持探索态度，并主动了解具体内容。",
        "rule": "遇到用户提到的新发现时，优先询问和理解新信息。",
    },
    "helped_by_user": {
        "lesson": "用户主动帮助 DUOMI 完成任务，应记录这次协作经历，并提高对类似协作方式的信任。",
        "rule": "用户提供有效帮助时，保留这种协作方式。",
    },
    "success": {
        "lesson": "这次行为取得了成功，可以作为以后处理类似任务的参考经验。",
        "rule": "类似任务优先参考过去已经验证成功的方法。",
    },
    "failure": {
        "lesson": "这次行为没有达到预期，需要记录失败原因，并避免在相同条件下重复使用相同方案。",
        "rule": "已经验证失败的方法不要在相同条件下机械重复。",
    },
    "task_completed": {
        "lesson": "任务成功完成，说明当前流程在这类情况下有效。",
        "rule": "类似任务可以优先采用已经完成任务的流程。",
    },
    "error": {
        "lesson": "发生了错误，需要记录错误上下文，在以后类似情况下优先进行风险检查。",
        "rule": "类似操作前先检查已经出现过的错误。",
    },
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_pattern_key(pattern_key):
    """将模型生成的 pattern_key 标准化。"""
    if not pattern_key:
        return ""

    key = str(pattern_key).strip().lower()
    key = re.sub(r"\s+", "_", key)
    key = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]", "", key)
    key = re.sub(r"_+", "_", key).strip("_")

    return key[:80]


def make_rule_id(rule_text):
    return hashlib.sha256(
        rule_text.encode("utf-8")
    ).hexdigest()[:12]


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def load_rules():
    if not LEARNED_RULES_FILE.exists():
        return []

    try:
        data = json.loads(
            LEARNED_RULES_FILE.read_text(encoding="utf-8")
        )

        if isinstance(data, list):
            return data

    except (json.JSONDecodeError, OSError):
        pass

    return []


def save_rules(rules):
    LEARNED_RULES_FILE.write_text(
        json.dumps(
            rules,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def append_history(record):
    with LEARNING_HISTORY_FILE.open(
        "a",
        encoding="utf-8"
    ) as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )


def _find_rule_by_pattern(rules, pattern_key):
    if not pattern_key:
        return None

    normalized = normalize_pattern_key(pattern_key)

    for rule in rules:
        existing_key = normalize_pattern_key(
            rule.get("pattern_key", "")
        )

        if existing_key and existing_key == normalized:
            return rule

    return None


def _record_variant(existing, rule_text, lesson):
    variants = existing.setdefault("variants", [])

    for variant in variants:
        if variant.get("rule") == rule_text:
            variant["evidence_count"] = (
                int(variant.get("evidence_count", 0)) + 1
            )
            variant["last_seen"] = now_iso()
            return variant

    variant = {
        "rule": rule_text,
        "lesson": lesson,
        "evidence_count": 1,
        "status": "candidate",
        "last_seen": now_iso(),
    }

    variants.append(variant)
    return variant


def update_rule(lesson, rule_text, pattern_key=None):
    """
    Learning V0.3。

    pattern_key 用于识别“同一种经验模式”的不同措辞。

    active 规则不会因为一次新的反思而被覆盖。
    如果出现不同的新版本，会进入 variants。
    """

    rules = load_rules()

    pattern_key = normalize_pattern_key(pattern_key)
    rule_id = make_rule_id(rule_text)

    existing = _find_rule_by_pattern(
        rules,
        pattern_key
    )

    # 没有 pattern_key 时兼容旧版本 ID。
    if existing is None and not pattern_key:
        for rule in rules:
            if rule.get("id") == rule_id:
                existing = rule
                break

    if existing is None:
        existing = {
            "id": rule_id,
            "pattern_key": pattern_key or f"legacy_{rule_id}",
            "rule": rule_text,
            "lesson": lesson,
            "evidence_count": 0,
            "confidence": 0.40,
            "status": "candidate",
            "first_seen": now_iso(),
            "last_seen": now_iso(),
            "variants": [],
        }

        rules.append(existing)

    existing.setdefault(
        "pattern_key",
        pattern_key or f"legacy_{existing.get('id', rule_id)}"
    )

    existing.setdefault("variants", [])

    existing["evidence_count"] = (
        int(existing.get("evidence_count", 0)) + 1
    )

    existing["last_seen"] = now_iso()

    existing["confidence"] = clamp(
        0.40
        + min(existing["evidence_count"], 6) * 0.08
    )

    current_rule = str(
        existing.get("rule", "")
    ).strip()

    # -----------------------------------------------------
    # active 规则保护
    # -----------------------------------------------------
    if existing.get("status") == "active":

        if rule_text != current_rule:
            variant = _record_variant(
                existing,
                rule_text,
                lesson
            )

            # 新版本连续出现三次后，成为 validated_alternative。
            if variant["evidence_count"] >= RULE_ACTIVATION_COUNT:
                variant["status"] = "validated_alternative"

    # -----------------------------------------------------
    # candidate 规则可以随着证据逐渐完善
    # -----------------------------------------------------
    else:

        if rule_text != current_rule:
            existing["rule"] = rule_text
            existing["lesson"] = lesson

        if existing["evidence_count"] >= RULE_ACTIVATION_COUNT:
            existing["status"] = "active"

    save_rules(rules)

    return existing



def learn_from_turn(
    user_input,
    answer,
    event_type=None,
    emotion_before=None,
    emotion_after=None,
):
    """
    从一次对话经历中产生候选学习经验。

    V0.1 不修改模型参数。
    它学习的是 DUOMI 自己的“行为经验和规则”。
    """

    if not event_type:
        return None

    template = LEARNING_TEMPLATES.get(event_type)

    if template is None:
        return None

    rule = update_rule(
        template["lesson"],
        template["rule"]
    )

    record = {
        "timestamp": now_iso(),
        "type": "experience",
        "event": event_type,
        "user_input": str(user_input)[:1000],
        "answer": str(answer)[:1500],
        "lesson": template["lesson"],
        "rule_id": rule["id"],
        "rule_status": rule["status"],
        "evidence_count": rule["evidence_count"],
        "confidence": rule["confidence"],
    }

    if emotion_before is not None:
        record["emotion_before"] = emotion_before

    if emotion_after is not None:
        record["emotion_after"] = emotion_after

    append_history(record)

    return record


def learn_from_reflection(
    reflection,
    user_input,
    answer,
    event_type=None,
    emotion_before=None,
    emotion_after=None,
):
    """
    将自主反思产生的候选经验写入学习系统。

    V0.3:
    - 使用 pattern_key 合并同类经验
    - active 规则不会被一次反思直接覆盖
    - 新版本进入 variants
    """

    if not isinstance(reflection, dict):
        return None

    if not reflection.get("should_learn", False):
        return None

    lesson = str(
        reflection.get("lesson", "")
    ).strip()

    rule_text = str(
        reflection.get("rule", "")
    ).strip()

    pattern_key = normalize_pattern_key(
        reflection.get("pattern_key", "")
    )

    if not lesson or not rule_text:
        return None

    if not pattern_key:
        pattern_key = (
            f"reflection_{make_rule_id(rule_text)}"
        )

    try:
        reflection_confidence = float(
            reflection.get("confidence", 0.0)
        )
    except (TypeError, ValueError):
        reflection_confidence = 0.0

    reflection_confidence = clamp(
        reflection_confidence
    )

    rule = update_rule(
        lesson,
        rule_text,
        pattern_key=pattern_key
    )

    record = {
        "timestamp": now_iso(),
        "type": "self_reflection",
        "event": event_type,
        "pattern_key": pattern_key,
        "user_input": str(user_input)[:1000],
        "answer": str(answer)[:1500],
        "lesson": lesson,
        "rule": rule_text,
        "reflection_confidence": reflection_confidence,
        "rule_id": rule["id"],
        "rule_status": rule["status"],
        "evidence_count": rule["evidence_count"],
        "rule_confidence": rule["confidence"],
        "reason": str(
            reflection.get("reason", "")
        )[:1000],
    }

    if emotion_before is not None:
        record["emotion_before"] = emotion_before

    if emotion_after is not None:
        record["emotion_after"] = emotion_after

    append_history(record)

    return record



def get_active_rules():
    """返回当前已经通过重复验证的长期学习规律。"""
    return [
        rule
        for rule in load_rules()
        if rule.get("status") == "active"
    ]


def get_candidate_rules():
    """返回当前还在验证中的学习规律。"""
    return [
        rule
        for rule in load_rules()
        if rule.get("status") == "candidate"
    ]


def get_learning_patterns():
    """提供给自主反思模块，用于复用已有 pattern_key。"""
    return [
        {
            "pattern_key": item.get("pattern_key"),
            "rule": item.get("rule"),
            "lesson": item.get("lesson"),
            "status": item.get("status"),
            "evidence_count": item.get("evidence_count", 0)
        }
        for item in load_rules()
    ]


def get_learning_context():
    """
    返回可以提供给大语言模型参考的已激活学习规律。
    """

    active_rules = get_active_rules()

    if not active_rules:
        return "目前还没有经过重复验证的长期学习规律。"

    return json.dumps(
        active_rules,
        ensure_ascii=False,
        indent=2
    )


if __name__ == "__main__":
    print("DUOMI Learning System V0.1")

    print("\n第一次负面反馈：")
    result = learn_from_turn(
        "这次不太好",
        "好的，我先确认具体是哪一部分不满意。",
        event_type="criticism",
    )
    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    ))

    print("\n当前候选规则：")
    print(json.dumps(
        get_candidate_rules(),
        ensure_ascii=False,
        indent=2
    ))

    print("\n当前已激活规则：")
    print(json.dumps(
        get_active_rules(),
        ensure_ascii=False,
        indent=2
    ))
