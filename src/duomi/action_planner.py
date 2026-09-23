import json
import os

from openai import OpenAI


class ActionPlanner:
    """DUOMI Action Planner V0.1"""

    ALLOWED_ACTIONS = {
        "forward",
        "backward",
        "left",
        "right",
        "stop",
    }

    MAX_DURATION = 3.0
    DEFAULT_DURATION = 0.5

    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )

    def plan(self, user_input: str):
        """
        判断用户输入是否包含明确的身体动作指令。

        返回：
            None

        或：
            {
                "action": "forward",
                "duration": 0.5
            }
        """

        prompt = f"""
你是 DUOMI 的动作规划器。

你的任务：
判断用户当前这句话是否明确要求 DUOMI 进行身体移动。

允许的动作只有：

forward  = 前进
backward = 后退
left     = 左转
right    = 右转
stop     = 停止

只有当用户明确要求 DUOMI 移动、转向或停止时，才生成动作。

如果只是普通聊天、提问、讨论、描述、开玩笑，
返回：

null

如果要求执行动作，只返回 JSON：

{{
  "action": "forward",
  "duration": 0.5
}}

规则：

1. action 只能是：
   forward、backward、left、right、stop

2. duration 必须是数字。

3. duration 最大为 {self.MAX_DURATION} 秒。

4. 如果用户明确给出“半秒”“1秒”等时间，
   按用户给出的时间转换。

5. 如果用户说“一下”“一点”“走走”等，
   使用保守默认时间 {self.DEFAULT_DURATION} 秒。

6. 如果用户要求“向前走1米”“后退2米”等距离，
   DUOMI 当前没有距离传感器或轮编码器，
   不能假装能够精确控制距离。
   请使用保守默认时间 {self.DEFAULT_DURATION} 秒。

7. stop 动作的 duration 必须为 0。

8. 不要生成超过最大持续时间的动作。

9. 只输出 JSON 或 null。
   不要解释。

用户输入：
{user_input}
"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-flash",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是 DUOMI 的动作规划器，"
                            "只输出合法 JSON 或 null。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )

            content = response.choices[0].message.content.strip()

            if content == "null":
                return None

            if content.startswith("```"):
                content = content.replace("```json", "")
                content = content.replace("```", "")
                content = content.strip()

            result = json.loads(content)

            if not isinstance(result, dict):
                return None

            action = result.get("action")

            if action not in self.ALLOWED_ACTIONS:
                return None

            # 停止动作固定为 0 秒
            if action == "stop":
                return {
                    "action": "stop",
                    "duration": 0.0,
                }

            try:
                duration = float(result.get("duration"))
            except (TypeError, ValueError):
                duration = self.DEFAULT_DURATION

            duration = max(
                0.0,
                min(duration, self.MAX_DURATION),
            )

            return {
                "action": action,
                "duration": duration,
            }

        except Exception as e:
            print(f"Action Planner 错误：{e}")
            return None
