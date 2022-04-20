import time

from pynisher import Pynisher


def func(number: int) -> int:
    """Test function."""
    for i in range(10):
        print(f"{i}. second")
        time.sleep(1)

    return number


if __name__ == "__main__":
    with Pynisher(func, nprocesses=3) as restricted_func:
        result = restricted_func(number=3)
        print(result)
