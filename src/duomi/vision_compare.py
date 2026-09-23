import json
import re
from pathlib import Path
from datetime import datetime


OBSERVATION_FILE = Path(
    "self_observation_memory.jsonl"
)

COMPARE_FILE = Path(
    "vision_comparison_memory.jsonl"
)


# =========================================================
# 物体名称归一化
# =========================================================

CANONICAL_RULES = [
    (
        "display",
        (
            "显示器",
            "屏幕",
            "电脑屏幕",
            "电脑显示器",
        ),
    ),

    (
        "desk",
        (
            "书桌",
            "桌面",
            "电脑桌",
            "木质桌",
            "木质书桌",
        ),
    ),

    (
        "water_bottle",
        (
            "水瓶",
            "水壶",
            "塑料水瓶",
            "透明塑料水瓶",
            "大号透明塑料水瓶",
        ),
    ),

    (
        "phone",
        (
            "手机",
            "移动电话",
        ),
    ),

    (
        "air_conditioner",
        (
            "空调",
            "壁挂式空调",
        ),
    ),

    (
        "door",
        (
            "门",
            "门框",
            "门 / 门框",
            "柜门",
        ),
    ),

    (
        "chair",
        (
            "椅子",
            "座椅",
        ),
    ),

    (
        "plastic_bag",
        (
            "塑料袋",
            "红色塑料袋",
            "橙色塑料袋",
            "红橙色塑料袋",
        ),
    ),

    (
        "fan",
        (
            "风扇",
            "吊扇",
            "风扇/吊扇",
        ),
    ),
]


def _text(value):
    return str(
        value or ""
    ).strip().lower()


def canonicalize_object(name):
    """
    将视觉模型不同的叫法映射到同一物体类别。
    """

    value = _text(name)

    for canonical, aliases in CANONICAL_RULES:

        for alias in aliases:

            if _text(alias) in value:
                return canonical

    # 删除描述性修饰后保留原始类别
    value = re.sub(
        r"[（）()【】\[\]，,：:／/]+",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        "",
        value
    )

    return value


def load_observations(limit=20):
    if not OBSERVATION_FILE.exists():
        return []

    records = []

    with OBSERVATION_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                item = json.loads(line)

                if isinstance(item, dict):
                    records.append(item)

            except json.JSONDecodeError:
                continue

    return records[-limit:]


def _object_map(objects):
    result = {}

    for obj in objects or []:

        if not isinstance(obj, dict):
            continue

        original_name = _text(
            obj.get("name")
        )

        if not original_name:
            continue

        canonical = canonicalize_object(
            original_name
        )

        count = obj.get(
            "count",
            1
        )

        try:
            count = int(count)
        except (
            TypeError,
            ValueError
        ):
            count = 1

        confidence = _text(
            obj.get(
                "confidence",
                "low"
            )
        )

        # 同一类别重复出现时合并数量
        if canonical in result:

            result[canonical]["count"] += count

            # high > medium > low
            order = {
                "high": 3,
                "medium": 2,
                "low": 1,
            }

            old_score = order.get(
                result[canonical]["confidence"],
                1
            )

            new_score = order.get(
                confidence,
                1
            )

            if new_score > old_score:
                result[canonical][
                    "confidence"
                ] = confidence

        else:

            result[canonical] = {
                "name": canonical,
                "original_names": [
                    original_name
                ],
                "count": count,
                "confidence": confidence,
            }

    return result


def _scene_overlap(
    previous,
    current,
):
    """
    用物体类别计算场景重叠程度。

    不是视觉定位，只是保守估计：
    如果两次观察共同看到的稳定物体很少，
    就不允许轻易下“消失”的结论。
    """

    old_map = _object_map(
        previous.get(
            "objects",
            []
        )
    )

    new_map = _object_map(
        current.get(
            "objects",
            []
        )
    )

    old_keys = set(
        old_map.keys()
    )

    new_keys = set(
        new_map.keys()
    )

    if not old_keys or not new_keys:
        return 0.0, old_keys, new_keys

    common = old_keys & new_keys

    denominator = max(
        len(old_keys),
        len(new_keys)
    )

    score = len(common) / denominator

    return score, old_keys, new_keys


def compare_observations(
    previous,
    current,
):
    old_map = _object_map(
        previous.get(
            "objects",
            []
        )
    )

    new_map = _object_map(
        current.get(
            "objects",
            []
        )
    )

    overlap, old_keys, new_keys = (
        _scene_overlap(
            previous,
            current
        )
    )

    appeared = []
    disappeared = []
    count_changed = []
    unchanged = []

    common = old_keys & new_keys

    for key in sorted(common):

        old_item = old_map[key]
        new_item = new_map[key]

        if (
            old_item["count"]
            == new_item["count"]
        ):

            unchanged.append({
                "object": key,
                "count": old_item["count"],
            })

        else:

            count_changed.append({
                "object": key,
                "previous_count": old_item["count"],
                "current_count": new_item["count"],
            })

    possible_appeared = (
        new_keys - old_keys
    )

    possible_disappeared = (
        old_keys - new_keys
    )

    # -----------------------------------------------------
    # 极其保守：
    #
    # 场景重叠 >= 0.60
    # 才允许报告出现/消失。
    #
    # 否则只说“无法确认”。
    # -----------------------------------------------------
    reliable_scene = (
        overlap >= 0.60
    )

    if reliable_scene:

        for key in sorted(
            possible_appeared
        ):
            appeared.append({
                "object": key,
                "current_count": new_map[key][
                    "count"
                ],
            })

        for key in sorted(
            possible_disappeared
        ):
            disappeared.append({
                "object": key,
                "previous_count": old_map[key][
                    "count"
                ],
            })

    # -----------------------------------------------------
    # 人物数量
    # -----------------------------------------------------
    old_people = (
        previous.get(
            "people",
            {}
        )
        or {}
    )

    new_people = (
        current.get(
            "people",
            {}
        )
        or {}
    )

    old_people_count = int(
        old_people.get(
            "count",
            0
        )
        or 0
    )

    new_people_count = int(
        new_people.get(
            "count",
            0
        )
        or 0
    )

    people_changed = (
        old_people_count
        != new_people_count
    )

    # -----------------------------------------------------
    # 文字
    # -----------------------------------------------------
    old_text = set(
        _text(x)
        for x in previous.get(
            "text",
            []
        )
        if _text(x)
    )

    new_text = set(
        _text(x)
        for x in current.get(
            "text",
            []
        )
        if _text(x)
    )

    text_added = sorted(
        new_text - old_text
    )

    text_removed = sorted(
        old_text - new_text
    )

    # -----------------------------------------------------
    # 最终结论
    # -----------------------------------------------------
    confirmed_changes = bool(
        count_changed
        or people_changed
        or (
            reliable_scene
            and (
                appeared
                or disappeared
            )
        )
        or text_added
        or text_removed
    )

    result = {
        "comparison_id": datetime.now().isoformat(
            timespec="seconds"
        ),

        "source": (
            "SELF_OBSERVATION_COMPARISON"
        ),

        "previous_observation_id": previous.get(
            "observation_id"
        ),

        "current_observation_id": current.get(
            "observation_id"
        ),

        "previous_timestamp": previous.get(
            "timestamp"
        ),

        "current_timestamp": current.get(
            "timestamp"
        ),

        "scene_overlap": round(
            overlap,
            3
        ),

        "comparison_reliability": (
            "high"
            if reliable_scene
            else "low"
        ),

        "appeared": appeared,

        "disappeared": disappeared,

        "count_changed": count_changed,

        "unchanged": unchanged,

        "people": {
            "previous_count": old_people_count,
            "current_count": new_people_count,
            "changed": people_changed,
        },

        "text": {
            "added": text_added,
            "removed": text_removed,
        },

        "cannot_determine": [
            "模型对同一物体可能使用不同名称",
            "没有目标检测框时不能可靠判断物体位置变化",
            "拍摄角度或视野变化时不能把未检测到当成消失",
            "不能根据两张描述判断人物身份",
            "不能仅凭单次视觉观察确认长期事实",
        ],
    }

    if not reliable_scene:
        result[
            "scene_warning"
        ] = (
            "两次观察的共同场景物体较少，"
            "可能存在视角、距离或画面范围变化。"
            "因此不报告物体的出现/消失，"
            "避免把视角变化误判为现实变化。"
        )

    result[
        "has_confirmed_change"
    ] = confirmed_changes

    return result


def save_comparison(result):
    with COMPARE_FILE.open(
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                result,
                ensure_ascii=False
            )
            + "\n"
        )


def print_comparison(result):

    print()
    print("=" * 70)
    print("DUOMI Vision Comparison V0.3.1")
    print("=" * 70)

    print(
        "上一次观察：",
        result.get(
            "previous_timestamp"
        )
    )

    print(
        "当前观察：",
        result.get(
            "current_timestamp"
        )
    )

    print()
    print(
        "场景重叠度：",
        result.get(
            "scene_overlap"
        )
    )

    print(
        "比较可靠性：",
        result.get(
            "comparison_reliability"
        )
    )

    if result.get(
        "scene_warning"
    ):
        print()
        print(
            "⚠️",
            result.get(
                "scene_warning"
            )
        )

    print()
    print("确定新增：")

    for item in result.get(
        "appeared",
        []
    ):
        print(
            "  +",
            item.get("object"),
            "×",
            item.get("current_count")
        )

    print()
    print("确定消失：")

    for item in result.get(
        "disappeared",
        []
    ):
        print(
            "  -",
            item.get("object"),
            "×",
            item.get("previous_count")
        )

    print()
    print("数量变化：")

    for item in result.get(
        "count_changed",
        []
    ):
        print(
            "  *",
            item.get("object"),
            ":",
            item.get("previous_count"),
            "→",
            item.get("current_count")
        )

    print()
    print("未变化：")

    for item in result.get(
        "unchanged",
        []
    ):
        print(
            "  =",
            item.get("object"),
            "×",
            item.get("count")
        )

    print()
    print("人物：")

    people = result.get(
        "people",
        {}
    )

    print(
        "  ",
        people.get(
            "previous_count"
        ),
        "→",
        people.get(
            "current_count"
        )
    )

    print()
    print("文字变化：")

    print(
        "  新出现：",
        result.get(
            "text",
            {}
        ).get(
            "added",
            []
        )
    )

    print(
        "  消失：",
        result.get(
            "text",
            {}
        ).get(
            "removed",
            []
        )
    )

    print()
    print("明确无法判断：")

    for item in result.get(
        "cannot_determine",
        []
    ):
        print(
            "  ·",
            item
        )

    print()
    print("=" * 70)


if __name__ == "__main__":

    observations = load_observations(
        limit=2
    )

    if len(observations) < 2:
        print(
            "⚠️ 当前 SELF_OBSERVATION "
            "少于 2 条。"
        )

        raise SystemExit(0)

    previous = observations[-2]
    current = observations[-1]

    result = compare_observations(
        previous,
        current
    )

    save_comparison(
        result
    )

    print_comparison(
        result
    )
