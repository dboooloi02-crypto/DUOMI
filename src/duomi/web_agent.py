import json

from web_tools import WEB_TOOLS, execute_tool


MODEL = "deepseek-flash"
MAX_TOOL_ROUNDS = 4


def ask_with_web_tools(client, messages):
    """
    DUOMI 联网问答模块。

    工作流程：
    1. 把当前对话交给 DeepSeek
    2. 模型自行判断是否需要调用联网工具
    3. 如果需要，执行 web_search / web_news / web_open
    4. 把工具结果返回给模型
    5. 重复直到模型给出最终回答
    """

    working_messages = list(messages)

    for _ in range(MAX_TOOL_ROUNDS):

        response = client.chat.completions.create(
            model=MODEL,
            messages=working_messages,
            tools=WEB_TOOLS,
            tool_choice="auto",

            # 当前先关闭 thinking。
            # 这样不需要额外处理 reasoning_content。
            extra_body={
                "thinking": {
                    "type": "disabled"
                }
            }
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        # 模型已经得到足够信息，直接回答。
        if not tool_calls:
            return message.content or ""

        # 必须把完整 assistant tool_calls 消息
        # 放回下一轮请求。
        working_messages.append(
            message.model_dump(
                exclude_none=True
            )
        )

        # 执行本轮全部工具调用。
        for tool_call in tool_calls:

            tool_name = tool_call.function.name
            raw_arguments = (
                tool_call.function.arguments or "{}"
            )

            try:
                arguments = json.loads(
                    raw_arguments
                )

                if not isinstance(
                    arguments,
                    dict
                ):
                    raise ValueError(
                        "工具参数必须是 JSON 对象"
                    )

            except Exception as exc:

                tool_result = {
                    "success": False,
                    "error": (
                        "工具参数解析失败："
                        f"{exc}"
                    )
                }

            else:

                try:
                    tool_result = execute_tool(
                        tool_name,
                        arguments
                    )

                except Exception as exc:

                    tool_result = {
                        "success": False,
                        "error": (
                            f"执行工具 {tool_name} 失败："
                            f"{exc}"
                        )
                    }

            result_text = json.dumps(
                tool_result,
                ensure_ascii=False
            )

            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text
                }
            )

    # 达到工具轮数后，强制模型只根据已经获得的资料回答，
    # 避免最后一次工具调用没有得到最终文本。
    final_response = client.chat.completions.create(
        model=MODEL,
        messages=working_messages,
        tools=WEB_TOOLS,
        tool_choice="none",

        extra_body={
            "thinking": {
                "type": "disabled"
            }
        }
    )

    return (
        final_response.choices[0].message.content
        or ""
    )
