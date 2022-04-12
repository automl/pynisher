from pynisher.pynisher import Pynisher


def func(number: int) -> int:
    """Test function."""
    return number


if __name__ == "__main__":
    with Pynisher(func) as restricted_func:
        result = restricted_func(number=3)

    print(result)
