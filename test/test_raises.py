from pynisher import Pynisher, contexts

import pytest


class CustomException(Exception):
    """A custom exception class"""

    pass


def _f() -> None:
    raise CustomException("Hello")


def test_raises_false() -> None:
    """
    Expects
    -------
    * Should raise no error even though the restricted function did
    """
    with Pynisher(_f, raises=False) as restricted_func:
        restricted_func()


@pytest.mark.parametrize("context", contexts)
def test_raises_true(context: str) -> None:
    """
    Expects
    -------
    * Should complete successfully if using less time than given
    """
    with Pynisher(_f, raises=True, context=context) as restricted_func:
        with pytest.raises(CustomException):
            restricted_func()
