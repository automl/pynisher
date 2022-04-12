from pynisher.pynisher import Pynisher


def func(number: int) -> int:
    """Test function."""
    return number


if __name__ == "__main__":
    with Pynisher(func, memory=1024, wall_time=120) as restricted_func:
        result = restricted_func(number=3)

    restricted_func = Pynisher(func, memory=1024)
    result = restricted_func.run(number=4)
