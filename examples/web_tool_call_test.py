#!/usr/bin/env python3

import os
import sys
import json

from openai import OpenAI
from web_tools import WEB_TOOLS, execute_tool


MODEL = "deepseek-flash"
MAX_TOOL_ROUNDS = 4


def run_agent(user_query):
    api_key = os.environ.get("DEEPSEEK_API_KEY")

    if not api_key:
        print("错误：没有找到 DEEPSEEK_API_KEY")
        return

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    messages = [
        {
            "role": "system",
            "content": (
                "你是 DUOMI 的 Web 工具测试代理。"
                "当用户询问最新消息或外部未知信息时，"
                "可以使用可用工具获取资料。"
                "拿到工具结果后，根据结果回答用户。"
                "不要编造没有出现在工具结果中的事实。"
            )
        },
        {
            "role": "user",
            "content": user_query
        }
    ]

    for round_no in range(1, MAX_TOOL_ROUNDS + 1):

        print()
        print(f"========== Round {round_no} ==========")

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=WEB_TOOLS,
                tool_choice="auto",

                # 测试阶段关闭 thinking，
                # 避免额外处理 reasoning_content。
                extra_body={
                    "thinking": {
                        "type": "disabled"
                    }
                }
            )

        except Exception as exc:
            print("DeepSeek API 错误：")
            print(exc)
            return

        message = response.choices[0].message

        print(
            "finish_reason:",
            response.choices[0].finish_reason
        )

        tool_calls = message.tool_calls or []

        # 没有工具调用，说明模型已经可以直接回答
        if not tool_calls:

            print()
            print("DUOMI：")
            print(message.content or "")
            return

        print(
            "本轮 Tool Call 数量：",
            len(tool_calls)
        )

        # 非常重要：
        # 必须先把完整 assistant tool_calls 消息加入 history
        assistant_message = message.model_dump(
            exclude_none=True
        )

        messages.append(
            assistant_message
        )

        # 然后逐个执行所有 tool call
        for index, tool_call in enumerate(
            tool_calls,
            1
        ):

            tool_name = tool_call.function.name
            raw_arguments = (
                tool_call.function.arguments
            )

            print()
            print(
                f"Tool Call {index}:"
            )
            print(
                "  name:",
                tool_name
            )
            print(
                "  arguments:",
                raw_arguments
            )

            try:
                arguments = json.loads(
                    raw_arguments
                )

            except json.JSONDecodeError as exc:

                tool_result = {
                    "success": False,
                    "error": (
                        "工具参数不是合法 JSON: "
                        f"{exc}"
                    )
                }

            else:

                tool_result = execute_tool(
                    tool_name,
                    arguments
                )

            result_text = json.dumps(
                tool_result,
                ensure_ascii=False
            )

            print(
                "  result_success:",
                tool_result.get("success")
            )

            if tool_name == "web_news":
                print(
                    "  source:",
                    tool_result.get("source")
                )
                print(
                    "  item_count:",
                    tool_result.get(
                        "count",
                        0
                    )
                )

            elif tool_name == "web_search":
                print(
                    "  backend:",
                    tool_result.get("backend")
                )
                print(
                    "  result_count:",
                    tool_result.get(
                        "result_count",
                        0
                    )
                )

            # 每一个 tool call 都必须有对应 tool message
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text
                }
            )

    print()
    print(
        f"已达到最大 Tool Call 轮数："
        f"{MAX_TOOL_ROUNDS}"
    )


def main():

    if len(sys.argv) >= 2:
        query = " ".join(
            sys.argv[1:]
        )
    else:
        query = input(
            "测试问题："
        ).strip()

    print("DUOMI DeepSeek Tool Call Test V0.1")
    print("问题：", query)

    run_agent(query)


if __name__ == "__main__":
    main()
