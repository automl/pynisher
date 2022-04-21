from contextlib import redirect_stderr
from pathlib import Path

from pynisher import Pynisher

import pytest


def f() -> int:
    """Simple function"""
    return 1


@pytest.mark.parametrize("warnings", [True, False])
def test_prints_to_std_err_with_warnings_true(tmp_path: Path, warnings: bool) -> None:
    """
    Expects
    -------
    * Expects the warnings to be printed to stderr
    """
    # We warn about memory limits being smaller than the limit
    # I tried a more direct approach by patching the __call__ but
    # that doesn't work as the wrapper __call__ then can not call
    # the real __call__
    # By using raises=False, we don't have to worry about errors
    path = tmp_path / "tmp.txt"

    with path.open("w") as fn, redirect_stderr(fn):
        rf = Pynisher(f, warnings=warnings, memory=(1, "KB"), raises=True)
        rf()

    with path.open("r") as fn:
        result = fn.readlines()

    assert any(result) == warnings
