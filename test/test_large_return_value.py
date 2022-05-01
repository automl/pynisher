from pynisher import contexts, limit
from pynisher.util import memconvert

import pytest


def return_large_value():
    """Just returns a very large value back"""
    big_size = memconvert(500, frm="MB")
    large_value = bytearray(big_size)
    return large_value


@pytest.mark.parametrize("context", contexts)
def test_large_return_value(context: str) -> None:
    """
    Expects
    -------
    * Python multiprocessing.connection.Connection say sending values
    larger than 32 MiB may result in a ValueError exception, depending
    on OS.
    """
    lf = limit(return_large_value)
    with pytest.raises(ValueError):
        lf()
