import json
import hashlib
from pathlib import Path
from datetime import datetime


OBSERVATION_FILE = Path(
    "self_observation_memory.jsonl"
)


def _now():
    return datetime.now().isoformat(
        timespec="seconds"
    )


def _safe_list(value):
    if isinstance(value, list):
        return value
    return []


def _image_hash(image_path):
    path = Path(image_path)

    if not path.exists():
        return None

    data = path.read_bytes()

    return hashlib.sha256(
        data
    ).hexdigest()[:16]


def build_self_observation(result):
    """
    把视觉系统结果转换成 SELF_OBSERVATION。

    注意：
    这里只记录“这次观察”。
    不写入 important_memory.json。
    """

    meta = result.get(
        "_meta",
        {}
    )

    image_path = meta.get(
        "image",
        ""
    )

    timestamp = meta.get(
        "timestamp"
    ) or _now()

    observation_id = (
        timestamp.replace(":", "")
        .replace("-", "")
        .replace("T", "_")
        + "_"
        + str(
            _image_hash(image_path)
            or "noimage"
        )
    )

    people = result.get(
        "people",
        {}
    )

    if not isinstance(people, dict):
        people = {}

    objects = []

    for obj in _safe_list(
        result.get("objects", [])
    ):
        if not isinstance(obj, dict):
            continue

        objects.append({
            "name": str(
                obj.get("name", "")
            ).strip(),
            "count": obj.get(
                "count",
                1
            ),
            "confidence": str(
                obj.get(
                    "confidence",
                    "low"
                )
            ).strip(),
        })

    observation = {
        "observation_id": observation_id,

        # 认知来源
        "source": "SELF_OBSERVATION",

        "type": "visual_observation",

        "timestamp": timestamp,

        "image": image_path,

        "image_hash": _image_hash(
            image_path
        ),

        # 当前视觉模型给出的总体描述
        "summary": str(
            result.get(
                "summary",
                ""
            )
        ).strip(),

        # 当前观察到的场景
        "scene": str(
            result.get(
                "scene",
                ""
            )
        ).strip(),

        # 观察到的物体
        "objects": objects,

        # 人的存在只记录观察结果
        # 不保存身份、年龄、性别推测
        "people": {
            "present": bool(
                people.get(
                    "present",
                    False
                )
            ),
            "count": people.get(
                "count",
                0
            ),
            "description": str(
                people.get(
                    "description",
                    ""
                )
            ).strip(),
        },

        # 能确认读出的文字
        "text": [
            str(x).strip()
            for x in _safe_list(
                result.get("text", [])
            )
            if str(x).strip()
        ],

        # 模型明确表示不确定的内容
        "uncertainties": [
            str(x).strip()
            for x in _safe_list(
                result.get(
                    "uncertainties",
                    []
                )
            )
            if str(x).strip()
        ],

        # 保留来源模型
        "model": meta.get(
            "model"
        ),
    }

    return observation


def save_self_observation(observation):
    """
    追加保存 SELF_OBSERVATION。
    """

    with OBSERVATION_FILE.open(
        "a",
        encoding="utf-8"
    ) as f:
        f.write(
            json.dumps(
                observation,
                ensure_ascii=False
            )
            + "\n"
        )


def load_observations(limit=20):
    """
    读取最近的视觉观察。
    """

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


def latest_observation():
    records = load_observations(1)

    if not records:
        return None

    return records[-1]


def print_observation_memory(
    observation
):
    print()
    print("=" * 70)
    print("DUOMI SELF_OBSERVATION")
    print("=" * 70)

    print(
        "观察 ID：",
        observation.get(
            "observation_id"
        )
    )

    print(
        "来源：",
        observation.get(
            "source"
        )
    )

    print(
        "时间：",
        observation.get(
            "timestamp"
        )
    )

    print(
        "图片：",
        observation.get(
            "image"
        )
    )

    print()
    print(
        "我观察到：",
        observation.get(
            "summary"
        )
    )

    print()
    print(
        "场景观察：",
        observation.get(
            "scene"
        )
    )

    print()
    print("物体：")

    for obj in observation.get(
        "objects",
        []
    ):
        print(
            "  ·",
            obj.get("name"),
            "×",
            obj.get("count"),
            "(",
            obj.get("confidence"),
            ")"
        )

    print()
    print(
        "人物数量：",
        observation.get(
            "people",
            {}
        ).get(
            "count",
            0
        )
    )

    print(
        "看到的文字：",
        observation.get(
            "text",
            []
        )
    )

    print()
    print("不确定：")

    for item in observation.get(
        "uncertainties",
        []
    ):
        print(
            "  ·",
            item
        )

    print()
    print("=" * 70)


if __name__ == "__main__":

    from vision_system import (
        observe
    )

    print("=" * 70)
    print("DUOMI Vision Memory V0.2")
    print("=" * 70)

    # 不重新调用视觉模型。
    # 直接读取 vision_system 最近一次真实观察。
    latest = None

    vision_log = Path(
        "vision_observation_log.jsonl"
    )

    if vision_log.exists():

        lines = [
            line.strip()
            for line in vision_log.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]

        if lines:
            try:
                latest = json.loads(
                    lines[-1]
                )
            except json.JSONDecodeError:
                latest = None

    if latest is None:
        print(
            "⚠️ 没有找到已有视觉观察，"
            "现在采集一张新图像。"
        )

        latest = observe(
            capture=True
        )

    observation = build_self_observation(
        latest
    )

    save_self_observation(
        observation
    )

    print_observation_memory(
        observation
    )

    print()
    print(
        "✅ SELF_OBSERVATION 已保存：",
        OBSERVATION_FILE
    )
