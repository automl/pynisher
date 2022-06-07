from pynisher import contexts, limit
from pynisher.util import memconvert

import pytest


def return_large_value() -> bytearray:
    """Just returns a very large value back"""
    big_size = int(memconvert(500, frm="MB"))
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

    Turns out this doesn't cause an issue but is extremely slow to send this
    information through a pipe. This is documented in the readme but the test left in
    case of future need.
    """
    pytest.skip(
        "This doesn't seem to raise errors on Linux but is extremely slow. Instead"
        " of enforicing behaviour, we simply warn users about return sizes being"
        " problematic and to instead write to file."
    )

    lf = limit(return_large_value)
    with pytest.raises(ValueError):
        lf()
