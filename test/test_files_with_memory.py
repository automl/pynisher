import platform
from pathlib import Path

from pynisher import MemoryLimitException, contexts, limit, supports
from pynisher.util import memconvert

import pytest

if not supports("memory"):
    pytest.skip(
        f"Doesn't support limiting memory on {platform.platform()} ",
        allow_module_level=True,
    )


def read_file(path: Path) -> bytes:
    """Reads in a byte file and return the bytes"""
    with path.open("rb") as f:
        return f.read()


@pytest.mark.parametrize("context", contexts)
def test_read_large_file(tmp_path: Path, context: str) -> None:
    """
    Expects
    -------
    * Reading files under memory limits should raise a memory limit exception
    """
    fpath = tmp_path / "bytefile.bytes"

    size = round(memconvert(100, frm="mb"))
    x = bytearray(size)
    with fpath.open("wb") as f:
        f.write(x)

    with limit(read_file, memory=(50, "mb")) as lf, pytest.raises(MemoryLimitException):
        lf(fpath)
