import os
import json
import signal

from openai import OpenAI
from tts_plus import speak_plus
from web_agent import ask_with_web_tools
from hearing import Hearing
from action_planner import ActionPlanner
from motor_controller import RobotController

from memory_manager import load_important_memory, save_important_memory, add_memory, update_memory, archive_memory, get_active_memories, retrieve_memories, link_memories
from emotion_system import apply_event, get_state, infer_event
from learning_system import learn_from_turn, get_learning_context
from reflection_system import reflect_on_turn
MEMORY_FILE = "memory.json"
PROFILE_FILE = "user_profile.json"
IMPORTANT_MEMORY_FILE = "important_memory.json"


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []


def load_profile():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}



def save_memory(messages):
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(messages, file, ensure_ascii=False, indent=2)


def organize_memory(client, conversation, important_memories):
    prompt = f"""
你是 DUOMI 的记忆整理模块。

请从下面的对话中提取值得长期保存的信息。

整理原则：
1. 只保存明确表达的事实。
2. 不要猜测用户没有说过的信息。
3. 普通闲聊不需要保存。
4. 如果信息已经存在，不要重复添加。
5. 重点关注用户身份、偏好、项目、目标和重要经历。
6. 如果新记忆与已有重要记忆存在明确关系，在 related_to 中填写对应的记忆 ID。
7. 只有存在明确关系时才填写 related_to，不要为了关联而强行建立关系。
8. 如果新信息与已有记忆表达的是同一件事，但内容发生了明确变化，使用 update。
9. update 时必须填写正确的已有记忆 ID。
10. 如果只是重复已有记忆，没有新的信息，使用 ignore。

已有重要记忆：
{json.dumps(important_memories, ensure_ascii=False, indent=2)}

本次对话：
{json.dumps(conversation, ensure_ascii=False, indent=2)}

请只返回 JSON 数组，不要添加其他文字。

每条信息必须包含：
- action：add、update 或 ignore
- type：记忆类型
- content：记忆内容
- importance：重要性
- target_id：当 action 为 update 时，填写要更新的已有记忆 ID；add 和 ignore 时填写 null
- related_to：与这条记忆明确相关的已有记忆 ID 列表

格式：
[
  {{
    "action": "add",
    "type": "user_preference",
    "content": "用户喜欢使用中文交流",
    "importance": "high",
    "target_id": null,
    "related_to": []
  }}
]
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个严谨的记忆整理程序，只输出合法 JSON。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = response.choices[0].message.content.strip()
        new_memories = json.loads(result)

        if isinstance(new_memories, list):
            for memory in new_memories:
                action = memory.get("action", "add")

                # 不需要保存
                if action == "ignore":
                    continue

                related_ids = memory.get("related_to", [])

                if not isinstance(related_ids, list):
                    related_ids = []

                # 只保留真正属于长期记忆的数据
                clean_memory = {
                    "type": memory.get("type", ""),
                    "content": memory.get("content", ""),
                    "importance": memory.get("importance", "normal"),
                    "related_to": related_ids
                }

                memory_id = None

                # 新增记忆
                if action == "add":
                    add_memory(
                        clean_memory,
                        important_memories
                    )

                    memory_id = clean_memory.get("id")

                # 更新已有记忆
                elif action == "update":
                    target_id = memory.get("target_id")

                    if not target_id:
                        continue

                    existing = next(
                        (
                            item
                            for item in important_memories
                            if item.get("id") == target_id
                        ),
                        None
                    )

                    if existing is None:
                        continue

                    # 保留旧关联，同时加入新的关联
                    merged_related = list(
                        existing.get("related_to", [])
                    )

                    for related_id in related_ids:
                        if (
                            related_id != target_id
                            and related_id not in merged_related
                        ):
                            merged_related.append(related_id)

                    clean_memory["related_to"] = merged_related

                    update_memory(
                        target_id,
                        clean_memory,
                        important_memories
                    )

                    memory_id = target_id

                # 未知 action 不处理
                else:
                    continue

                # 建立双向关联
                if memory_id:
                    for related_id in clean_memory["related_to"]:
                        if related_id != memory_id:
                            link_memories(
                                memory_id,
                                related_id,
                                important_memories
                            )

            print("DUOMI：本次记忆整理完成")

    except Exception as e:
        print(f"记忆整理失败：{e}")


def main():
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )

    hearing = Hearing()
    action_planner = ActionPlanner()
    robot = RobotController()

    profile = load_profile()
    important_memories = load_important_memory()

    messages = [
        {
            "role": "system",
            "content": f"""你是 DUOMI，一个正在成长的具身智能机器人。

    用户档案：
    {json.dumps(profile, ensure_ascii=False, indent=2)}

    请根据用户档案和后续提供的相关记忆理解用户，不要凭空编造信息。
    当用户询问最新消息、当前情况、近期变化，或者问题涉及你无法可靠确定的外部信息时，可以使用可用的联网工具获取资料。
    普通聊天和你已有可靠知识能够回答的问题，不必强行联网。
    使用联网工具获得资料后，应根据资料回答，不要编造工具没有提供的信息。"""
        }
    ]

    messages.extend(load_memory())

    def handle_sigint(signum, frame):
        print("\n")
        print("DUOMI：收到系统中断，正在停止身体...")

        try:
            robot.stop()
        except Exception:
            pass

        print("DUOMI：身体已停止")
        print("DUOMI：系统关闭")

        raise SystemExit(130)

    signal.signal(signal.SIGINT, handle_sigint)

    print("DUOMI AI 核心系统启动")
    print("已加载历史记忆")
    print("说“退出系统”退出 DUOMI")
    print("紧急停止：Ctrl+C")

    while True:
        print()
        print("DUOMI 正在聆听……")

        user_input = hearing.listen_once()

        if not user_input:
            continue

        print(f"你：{user_input}")

        if user_input.lower() in {"quit", "退出", "退出系统"}:
            save_memory(messages[1:])
            robot.stop()
            hearing.close()
            robot.close()
            print("DUOMI：记忆已保存，系统关闭")
            break

        # -----------------------------
        # Agency / Action Planner V0.1
        # -----------------------------
        action_plan = action_planner.plan(user_input)

        if action_plan:
            action = action_plan["action"]
            duration = action_plan["duration"]

            print(
                f"DUOMI 动作：{action} / "
                f"{duration:.2f} 秒"
            )

            try:
                robot.execute(
                    action,
                    duration,
                )

                action_messages = {
                    "forward": "好的，我向前走了一下。",
                    "backward": "好的，我向后退了一下。",
                    "left": "好的，我向左转了一下。",
                    "right": "好的，我向右转了一下。",
                    "stop": "好的，停止。",
                }

                answer = action_messages.get(
                    action,
                    "好的，动作完成。"
                )

                print(f"DUOMI：{answer}")
                speak_plus(answer)

                messages.append({
                    "role": "user",
                    "content": user_input
                })

                messages.append({
                    "role": "assistant",
                    "content": answer
                })

                save_memory(messages[1:])

                print("DUOMI：动作已完成")

                continue

            except Exception as e:
                robot.stop()
                print(f"DUOMI 身体动作失败：{e}")
                continue
        # -----------------------------
        # Emotion V0.1
        # 根据用户明确表达更新 DUOMI 内部状态。
        # 普通聊天不强行改变情绪。
        # -----------------------------
        # -----------------------------
        # Emotion V0.1
        # -----------------------------
        emotion_before = get_state()
        detected_event = infer_event(user_input)
        event_type = None

        if detected_event:
            event_type, intensity = detected_event

            emotion_state = apply_event(
                event_type,
                intensity=intensity,
                reason=user_input[:200]
            )
        else:
            emotion_state = emotion_before

        related_memories = retrieve_memories(
            user_input,
            important_memories
        )

        memory_context = {
            "role": "system",
            "content": f"""与当前问题相关的长期记忆：

{json.dumps(related_memories, ensure_ascii=False, indent=2)}

请仅参考这些相关记忆理解用户。

如果存在多条相关记忆，请结合它们之间可能存在的关系一起理解，而不是把它们完全分开看。

不要凭空创造记忆中不存在的事实或关系。"""
        }

        emotion_context = {
            "role": "system",
            "content": f"""DUOMI 当前内部状态：

{json.dumps(emotion_state, ensure_ascii=False, indent=2)}

这些数据属于 DUOMI 的内部状态，不是外部事实。
请将其作为回答时的内部参考，例如调整语气、谨慎程度和探索倾向。

不要因为这些状态就凭空编造事实。
除非用户主动询问，否则不要主动向用户展示内部数值。"""
        }

        # -----------------------------
        # Learning V0.1
        # 每轮重新读取当前已经激活的学习规律，
        # 这样本次运行中新形成的规律也能立即用于下一轮。
        # -----------------------------
        learning_context = {
            "role": "system",
            "content": f"""DUOMI 已经从过去经历中形成的学习规律：

{get_learning_context()}

这些规律只是 DUOMI 根据过去经历形成的行为经验，不是绝对事实。
只有在当前情境相关时才参考。
如果当前事实与历史经验冲突，应以当前事实和当前用户输入为准。
不要主动向用户展示内部学习规则。"""
        }

        messages.append({
            "role": "user",
            "content": user_input
        })

        request_messages = messages + [
            memory_context,
            emotion_context,
            learning_context
        ]

        try:
            answer = ask_with_web_tools(
                client,
                request_messages
            )

            print(f"DUOMI：{answer}")

            # 先完成语音输出，避免自主反思增加用户等待时间。
            speak_plus(answer)

            # -----------------------------
            # Learning V0.2
            # 自主反思：
            # 让 DeepSeek 根据真实经历提炼学习候选。
            # -----------------------------
            if event_type:
                reflection = reflect_on_turn(
                    client=client,
                    user_input=user_input,
                    answer=answer,
                    event_type=event_type,
                    emotion_before=emotion_before,
                    emotion_after=emotion_state,
                )

                # 反思成功：使用模型自主提炼的经验。
                if reflection is not None:
                    from learning_system import learn_from_reflection

                    learned = learn_from_reflection(
                        reflection=reflection,
                        user_input=user_input,
                        answer=answer,
                        event_type=event_type,
                        emotion_before=emotion_before,
                        emotion_after=emotion_state,
                    )

                    if learned:
                        print("DUOMI：本轮自主反思已记录")

                # 反思失败：退回 V0.1 的保守模板学习。
                else:
                    learn_from_turn(
                        user_input=user_input,
                        answer=answer,
                        event_type=event_type,
                        emotion_before=emotion_before,
                        emotion_after=emotion_state,
                    )

            messages.append({
                "role": "assistant",
                "content": answer
            })

            save_memory(messages[1:])

            organize_memory(
                client,
                messages[-2:],
                important_memories
            )

        except Exception as e:
            print(f"调用 AI 失败：{e}")
            messages.pop()


if __name__ == "__main__":
    main()
