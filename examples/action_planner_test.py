from action_planner import ActionPlanner


planner = ActionPlanner()

tests = [
    "多米向前走半秒",
    "多米后退一下",
    "多米向左转",
    "多米停下来",
    "你好多米，你今天怎么样",
]

for text in tests:
    result = planner.plan(text)

    print()
    print("用户：", text)
    print("规划：", result)
