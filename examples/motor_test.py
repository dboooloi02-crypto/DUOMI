from gpiozero import DigitalOutputDevice
from time import sleep

ENA = DigitalOutputDevice(23)
IN1 = DigitalOutputDevice(17)
IN2 = DigitalOutputDevice(18)

try:
    print("马达测试开始")

    print("使能")
    ENA.on()

    print("正转")
    IN1.on()
    IN2.off()
    sleep(2)

    print("停止")
    IN1.off()
    IN2.off()
    sleep(1)

    print("反转")
    IN1.off()
    IN2.on()
    sleep(2)

    print("停止")
    IN1.off()
    IN2.off()
    ENA.off()

    print("测试完成")

finally:
    IN1.off()
    IN2.off()
    ENA.off()
