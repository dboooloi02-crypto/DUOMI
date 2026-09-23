import os
import json
import base64
import subprocess
from pathlib import Path
from datetime import datetime

from openai import OpenAI


# =========================================================
# DUOMI Vision System V0.1
# =========================================================

DEFAULT_DEVICE = "/dev/video0"
DEFAULT_IMAGE = "camera_test.jpg"
VISION_MODEL = "deepseek-flash"

_api_key = os.environ.get("DEEPSEEK_API_KEY")

if not _api_key:
    raise RuntimeError(
        "❌ 没有找到 DEEPSEEK_API_KEY。"
        "请先在当前终端设置 DeepSeek API Key。"
    )

client = OpenAI(
    api_key=_api_key,
    base_url="https://api.deepseek.com",
)


def capture_frame(
    device=DEFAULT_DEVICE,
    output=None,
):
    """
    从 USB 摄像头抓取一帧 JPEG。

    V0.3.1：
    每次采集保存独立图片，
    不再覆盖历史观察。
    """

    if output is None:
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        frame_dir = Path(
            "vision_frames"
        )

        frame_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        output = str(
            frame_dir
            / f"frame_{timestamp}.jpg"
        )

    command = [
        "v4l2-ctl",
        "-d",
        device,
        "--stream-mmap",
        "--stream-count=1",
        f"--stream-to={output}",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "❌ 摄像头采集失败：\n"
            + result.stderr
        )

    path = Path(output)

    if not path.exists():
        raise RuntimeError(
            "❌ 摄像头采集完成，但没有找到图片文件。"
        )

    if path.stat().st_size == 0:
        raise RuntimeError(
            "❌ 摄像头生成了空图片。"
        )

    return str(path)


def _image_to_data_url(image_path):
    """
    将本地 JPEG 转成 DeepSeek 可接收的 base64 data URL。
    """

    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(
            f"找不到图片：{image_path}"
        )

    image_bytes = path.read_bytes()

    encoded = base64.b64encode(
        image_bytes
    ).decode("ascii")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


def _clean_json(text):
    text = str(text or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return text


def analyze_image(
    image_path,
    question=None,
):
    """
    让 DUOMI 对图片进行视觉理解。

    注意：
    只描述图像中实际能确认的内容。
    看不清就明确说“不确定”。
    """

    data_url = _image_to_data_url(
        image_path
    )

    if question is None:
        question = (
            "这是我通过摄像头看到的现实世界画面。"
            "请告诉我，我实际看到了什么。"
        )

    prompt = f"""
你现在是 DUOMI 的视觉感知系统。

请分析我通过摄像头输入的这张图片。

你的最高原则是：
【只描述图片中能够确认的内容，不要猜测。】

如果画面模糊、太暗、分辨率不足，必须明确告诉我“不确定”。

不要把：
- 推测
- 常识
- 用户可能是谁
- 图片外的信息

当成图片事实。

请特别关注：

1. 整体场景
2. 可以确认的物体
3. 人是否存在
4. 可以读取的文字
5. 明显的空间结构
6. 看不清或无法确定的内容

用户当前想知道：
{question}

只返回合法 JSON：

{{
  "summary": "对整个画面的客观描述",
  "objects": [
    {{
      "name": "物体名称",
      "count": 1,
      "confidence": "high / medium / low"
    }}
  ],
  "people": {{
    "present": false,
    "count": 0,
    "description": ""
  }},
  "text": [],
  "scene": "",
  "uncertainties": [
    "无法确认的内容"
  ]
}}
"""

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是 DUOMI 的视觉感知系统。"
                    "必须区分观察事实与推测。"
                    "看不清就说不确定。"
                    "不要编造图片中不存在的内容。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                        },
                    },
                ],
            },
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content
    cleaned = _clean_json(raw)

    try:
        result = json.loads(cleaned)
    except Exception:
        # 如果模型返回的不是 JSON，保留原始观察
        result = {
            "summary": raw,
            "objects": [],
            "people": {
                "present": False,
                "count": 0,
                "description": "",
            },
            "text": [],
            "scene": "",
            "uncertainties": [
                "模型没有返回标准 JSON"
            ],
        }

    if not isinstance(result, dict):
        result = {
            "summary": str(result),
            "objects": [],
            "people": {
                "present": False,
                "count": 0,
                "description": "",
            },
            "text": [],
            "scene": "",
            "uncertainties": [],
        }

    result["_meta"] = {
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "image": str(image_path),
        "model": VISION_MODEL,
    }

    return result


def save_observation(result):
    """
    保存原始视觉观察记录。
    与 important_memory.json 分开。
    """

    log_path = Path(
        "vision_observation_log.jsonl"
    )

    with log_path.open(
        "a",
        encoding="utf-8"
    ) as f:
        f.write(
            json.dumps(
                result,
                ensure_ascii=False,
            )
            + "\n"
        )


def observe(
    image_path=None,
    capture=True,
    device=DEFAULT_DEVICE,
):
    """
    完整视觉流程：

    摄像头
      ↓
    图片
      ↓
    DeepSeek Vision
      ↓
    视觉观察
      ↓
    独立观察日志
    """

    if capture:
        image_path = capture_frame(
            device=device,
            output=image_path,
        )

    elif not image_path:
        image_path = DEFAULT_IMAGE

    result = analyze_image(
        image_path
    )

    save_observation(
        result
    )

    return result


def print_observation(result):
    print()
    print("=" * 70)
    print("DUOMI 视觉观察")
    print("=" * 70)

    meta = result.get(
        "_meta",
        {}
    )

    print(
        "图片：",
        meta.get("image")
    )

    print(
        "模型：",
        meta.get("model")
    )

    print()
    print(
        "我看到：",
        result.get("summary", "")
    )

    print()
    print(
        "场景：",
        result.get("scene", "")
    )

    print()
    print("物体：")

    for obj in result.get(
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
    print("人物：")

    people = result.get(
        "people",
        {}
    )

    print(
        "  是否存在：",
        people.get("present")
    )

    print(
        "  数量：",
        people.get("count")
    )

    if people.get("description"):
        print(
            "  描述：",
            people.get("description")
        )

    print()
    print("图片文字：")

    for text in result.get(
        "text",
        []
    ):
        print(
            "  ·",
            text
        )

    print()
    print("我不确定：")

    for uncertainty in result.get(
        "uncertainties",
        []
    ):
        print(
            "  ·",
            uncertainty
        )

    print()
    print("=" * 70)


if __name__ == "__main__":

    print("=" * 70)
    print("DUOMI Vision System V0.1")
    print("=" * 70)

    result = observe(
        image_path="camera_test.jpg",
        capture=False,
    )

    print_observation(
        result
    )
