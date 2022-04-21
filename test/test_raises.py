from pynisher import Pynisher

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


def test_raises_true() -> None:
    """
    Expects
    -------
    * Should complete successfully if using less time than given
    """
    with Pynisher(_f, raises=True) as restricted_func:
        with pytest.raises(CustomException):
            restricted_func()
