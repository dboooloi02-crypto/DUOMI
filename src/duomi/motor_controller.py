from time import sleep, monotonic
from gpiozero import DigitalOutputDevice


class Motor:
    """单个直流减速电机"""

    def __init__(self, enable_pin: int, in1_pin: int, in2_pin: int):
        self.enable = DigitalOutputDevice(enable_pin)
        self.in1 = DigitalOutputDevice(in1_pin)
        self.in2 = DigitalOutputDevice(in2_pin)

        self.stop()

    def forward(self):
        self.enable.on()
        self.in1.on()
        self.in2.off()

    def backward(self):
        self.enable.on()
        self.in1.off()
        self.in2.on()

    def stop(self):
        self.in1.off()
        self.in2.off()
        self.enable.off()

    def close(self):
        self.stop()
        self.enable.close()
        self.in1.close()
        self.in2.close()


class RobotController:
    """
    DUOMI Body V0.1

    左轮：
        ENA  -> GPIO23
        IN1  -> GPIO17
        IN2  -> GPIO18

    右轮：
        ENB  -> GPIO24
        IN3  -> GPIO27
        IN4  -> GPIO22
    """

    # 单次动作最大允许时间
    MAX_ACTION_DURATION = 3.0

    def __init__(self):
        self.left = Motor(
            enable_pin=23,
            in1_pin=17,
            in2_pin=18,
        )

        self.right = Motor(
            enable_pin=24,
            in1_pin=27,
            in2_pin=22,
        )

        self.current_action = "stop"

    def forward(self):
        """前进"""
        self.left.forward()
        self.right.forward()
        self.current_action = "forward"

    def backward(self):
        """后退"""
        self.left.backward()
        self.right.backward()
        self.current_action = "backward"

    def left_turn(self):
        """原地左转"""
        self.left.backward()
        self.right.forward()
        self.current_action = "left_turn"

    def right_turn(self):
        """原地右转"""
        self.left.forward()
        self.right.backward()
        self.current_action = "right_turn"

    def stop(self):
        """停止"""
        self.left.stop()
        self.right.stop()
        self.current_action = "stop"

    def execute(self, action: str, duration: float = 0.5):
        """
        执行动作指定时间。

        duration 会被限制在：
        0 ~ MAX_ACTION_DURATION 秒
        """

        duration = max(0.0, min(float(duration), self.MAX_ACTION_DURATION))

        actions = {
            "forward": self.forward,
            "backward": self.backward,
            "left": self.left_turn,
            "left_turn": self.left_turn,
            "right": self.right_turn,
            "right_turn": self.right_turn,
            "stop": self.stop,
        }

        if action not in actions:
            raise ValueError(f"未知动作: {action}")

        actions[action]()

        if action == "stop":
            return

        start = monotonic()

        try:
            while monotonic() - start < duration:
                sleep(0.01)
        finally:
            # 无论发生什么，都自动停止
            self.stop()

    def close(self):
        self.stop()
        self.left.close()
        self.right.close()


def keyboard_control():
    """
    DUOMI Body V0.1 键盘测试

    W = 前进
    S = 后退
    A = 左转
    D = 右转
    空格 = 停止
    Q = 退出
    """

    import sys
    import tty
    import termios

    robot = RobotController()

    old_settings = termios.tcgetattr(sys.stdin)

    print()
    print("================================")
    print(" DUOMI Body V0.1 键盘控制")
    print("================================")
    print("W = 前进")
    print("S = 后退")
    print("A = 左转")
    print("D = 右转")
    print("空格 = 停止")
    print("Q = 退出")
    print("--------------------------------")
    print("每次移动 0.3 秒")
    print()

    try:
        tty.setcbreak(sys.stdin.fileno())

        while True:
            key = sys.stdin.read(1).lower()

            if key == "w":
                print("前进")
                robot.execute("forward", 0.3)

            elif key == "s":
                print("后退")
                robot.execute("backward", 0.3)

            elif key == "a":
                print("左转")
                robot.execute("left_turn", 0.3)

            elif key == "d":
                print("右转")
                robot.execute("right_turn", 0.3)

            elif key == " ":
                print("停止")
                robot.stop()

            elif key == "q":
                print("退出")
                break

    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，停止机器人")

    finally:
        robot.stop()
        robot.close()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    keyboard_control()
