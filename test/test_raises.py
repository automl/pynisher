from pynisher import Pynisher, contexts

import pytest

from test.util import raises_error


class CustomException(Exception):
    """A custom exception class"""

    pass


@pytest.mark.parametrize("context", contexts)
def test_raises_false(context: str) -> None:
    """
    Expects
    -------
    * Should raise no error even though the restricted function did
    """
    with Pynisher(raises_error, raises=False, context=context) as rf:
        rf()


@pytest.mark.parametrize("context", contexts)
def test_raises_true(context: str) -> None:
    """
    Expects
    -------
    * Should complete successfully if using less time than given
    """
    with Pynisher(raises_error, raises=True, context=context) as rf:
        with pytest.raises(CustomException):
            rf(CustomException)
