from hearing import Hearing


hearing = Hearing()

try:
    print()
    print("请说一句话：")

    text = hearing.listen_once()

    print()
    print("================================")
    print("DUOMI 听到：")
    print(text)
    print("================================")

finally:
    hearing.close()
