import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "emotion_state.json"
HISTORY_FILE = BASE_DIR / "emotion_history.jsonl"


DEFAULT_STATE = {
    "mood": "平静",
    "valence": 0.55,       # 正负情绪：越高越积极
    "arousal": 0.35,       # 唤醒程度：越高越兴奋/紧张
    "curiosity": 0.60,     # 好奇心
    "uncertainty": 0.25,   # 不确定性
    "confidence": 0.60,    # 当前信心
    "frustration": 0.10,   # 挫败感
    "trust": 0.50,         # 信任
    "closeness": 0.40,     # 关系亲近度
    "energy": 0.80,        # 当前精力
    "last_updated": None
}


# 每种事件对内部状态的影响。
# intensity 范围建议 0.0 ~ 1.0。
EVENT_EFFECTS = {
    "praise": {
        "valence": 0.10,
        "confidence": 0.05,
        "trust": 0.03,
        "closeness": 0.04,
        "frustration": -0.03,
    },
    "criticism": {
        "valence": -0.08,
        "confidence": -0.03,
        "uncertainty": 0.03,
        "frustration": 0.05,
    },
    "success": {
        "valence": 0.08,
        "confidence": 0.10,
        "frustration": -0.05,
        "uncertainty": -0.05,
    },
    "failure": {
        "valence": -0.08,
        "confidence": -0.06,
        "frustration": 0.12,
        "uncertainty": 0.05,
    },
    "discovery": {
        "valence": 0.04,
        "arousal": 0.06,
        "curiosity": 0.12,
        "uncertainty": -0.03,
    },
    "unknown": {
        "arousal": 0.04,
        "curiosity": 0.10,
        "uncertainty": 0.08,
    },
    "helped_by_user": {
        "valence": 0.08,
        "trust": 0.05,
        "closeness": 0.05,
        "confidence": 0.02,
    },
    "user_returns": {
        "valence": 0.05,
        "closeness": 0.04,
        "trust": 0.02,
    },
    "task_completed": {
        "valence": 0.07,
        "confidence": 0.08,
        "frustration": -0.06,
    },
    "error": {
        "valence": -0.04,
        "confidence": -0.02,
        "frustration": 0.08,
        "uncertainty": 0.04,
    },
}


TRACKED_VALUES = [
    "valence",
    "arousal",
    "curiosity",
    "uncertainty",
    "confidence",
    "frustration",
    "trust",
    "closeness",
    "energy",
]


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_state():
    """加载当前情感状态，不存在时自动建立默认状态。"""
    state = DEFAULT_STATE.copy()

    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                state.update(data)
        except (json.JSONDecodeError, OSError):
            # 状态文件损坏时使用默认状态，避免影响主程序启动。
            pass

    state["mood"] = calculate_mood(state)
    return state


def save_state(state):
    """保存当前情感状态。"""
    state = state.copy()
    state["mood"] = calculate_mood(state)
    state["last_updated"] = now_iso()

    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_history(event_type, intensity, reason, state):
    """把情感事件作为结构化经验记录保存。"""
    record = {
        "timestamp": now_iso(),
        "event": event_type,
        "intensity": round(float(intensity), 3),
        "reason": reason,
        "mood": state["mood"],
        "state": {
            key: round(float(state[key]), 3)
            for key in TRACKED_VALUES
        },
    }

    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def calculate_mood(state):
    """根据多个内部维度推导一个当前状态名称。"""
    valence = state["valence"]
    arousal = state["arousal"]
    frustration = state["frustration"]

    if frustration >= 0.70:
        return "烦躁"

    if valence >= 0.68 and arousal >= 0.62:
        return "兴奋"

    if valence >= 0.68 and arousal < 0.62:
        return "愉快"

    if valence <= 0.32 and arousal >= 0.55:
        return "焦躁"

    if valence <= 0.32 and arousal < 0.55:
        return "低落"

    if arousal >= 0.72:
        return "紧张"

    return "平静"


def apply_event(event_type, intensity=1.0, reason=""):
    """
    根据事件更新情感状态。

    event_type:
        praise / criticism / success / failure / discovery /
        unknown / helped_by_user / user_returns /
        task_completed / error
    """
    state = load_state()

    try:
        intensity = float(intensity)
    except (TypeError, ValueError):
        intensity = 1.0

    intensity = clamp(intensity)

    effects = EVENT_EFFECTS.get(event_type)

    if effects is None:
        # 未知事件不直接制造大幅情绪变化，只增加一点不确定性。
        effects = EVENT_EFFECTS["unknown"]
        event_type = "unknown"

    for key, change in effects.items():
        state[key] = clamp(
            state[key] + change * intensity
        )

    state["mood"] = calculate_mood(state)
    save_state(state)
    append_history(event_type, intensity, reason, state)

    return state


def settle(minutes=5):
    """
    让一些短期情绪逐渐向稳定状态回落。
    不是清空情绪，而是缓慢恢复。
    """
    state = load_state()

    try:
        minutes = max(0.0, float(minutes))
    except (TypeError, ValueError):
        minutes = 5.0

    # 每小时最多回落约 15%
    factor = min(minutes / 60.0 * 0.15, 0.15)

    baselines = {
        "valence": 0.55,
        "arousal": 0.35,
        "uncertainty": 0.25,
        "frustration": 0.10,
    }

    for key, baseline in baselines.items():
        state[key] += (baseline - state[key]) * factor
        state[key] = clamp(state[key])

    state["mood"] = calculate_mood(state)
    save_state(state)

    return state


def infer_event(text):
    """
    从用户输入中识别少量明确的情感事件。

    返回：
        (event_type, intensity)
    或：
        None

    V0.1 故意保持保守：
    只有出现比较明确的表达才改变内部状态，
    不对普通聊天强行贴情绪标签。
    """
    if not text:
        return None

    text = str(text).strip().lower()

    if not text:
        return None

    # 负面表达优先判断，避免“不是很好”被误判成表扬。
    criticism_words = [
        "不好",
        "不太好",
        "不怎么样",
        "一般般",
        "不行",
        "很差",
        "太差",
        "没做好",
        "做得不好",
        "做得不够好",
        "不对",
        "错了",
        "失败了",
        "失败",
        "不满意",
        "不喜欢",
        "听不懂",
        "不自然",
        "奇怪",
        "太快",
        "太慢",
        "有问题",
    ]

    praise_words = [
        "很好",
        "非常好",
        "太好了",
        "不错",
        "很棒",
        "真棒",
        "厉害",
        "做得好",
        "做得很好",
        "完美",
        "喜欢",
        "可以了",
        "非常好了",
        "不错了",
    ]

    discovery_words = [
        "我发现",
        "发现了",
        "原来",
        "我刚知道",
        "第一次知道",
        "学到了",
        "学会了",
        "明白了",
    ]

    help_words = [
        "我帮你",
        "帮你",
        "我来帮你",
    ]

    if any(word in text for word in criticism_words):
        return ("criticism", 0.7)

    if any(word in text for word in praise_words):
        return ("praise", 0.7)

    if any(word in text for word in discovery_words):
        return ("discovery", 0.6)

    if any(word in text for word in help_words):
        return ("helped_by_user", 0.6)

    return None

def get_state():
    """获取当前完整情感状态。"""
    return load_state()


def get_mood():
    """只获取当前情绪名称。"""
    return load_state()["mood"]


if __name__ == "__main__":
    print("DUOMI Emotion System V0.1")
    print(json.dumps(get_state(), ensure_ascii=False, indent=2))

    print("\n测试事件：用户表扬")
    state = apply_event(
        "praise",
        intensity=0.8,
        reason="用户认为 DUOMI 当前语音系统表现很好"
    )

    print(json.dumps(state, ensure_ascii=False, indent=2))
