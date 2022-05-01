"""
Import sklearn without enough memory causes errors to be raised but these are platform
specific. To tackle this problem, pynisher will raise a general PynisherException but
individual errors types can be raised as a MemoryLimitException.
"""
import os
import sys

from pynisher import MemoryLimitException, PynisherException, limit
from pynisher.util import Monitor

import pytest

# My local machine was complaining and then gave a sigsegv, raising a PynisherException
# This prevents it
os.environ["OPENBLAS_NUM_THREADS"] = "1"

plat = sys.platform.lower()


def import_sklearn() -> bool:
    """Just imports sklearn"""
    m = Monitor()
    print("Before import ", m.memory("mb"))

    import sklearn  # noqa

    print("After import ", m.memory("mb"))

    return True


@pytest.mark.skipif(not plat.startswith("linux"), reason="linux specific")
def test_import_fail_linux() -> None:
    """
    Expects
    -------
    * Should fail to import if the memory limit is too low

    Note
    ----
    For sklearn on linux, this triggers an ImportError and so we have
    to be aware of it before hand. There's no automatic way to identfiy
    this from a regular ImportError so we better be explicit about it.
    """
    with pytest.raises(MemoryLimitException):
        with limit(
            import_sklearn,
            memory=(100, "mb"),
            wrap_errors={"memory": [ImportError]},
        ) as lf:
            lf()


@pytest.mark.skipif(not plat.startswith("win"), reason="windows specific")
def test_import_fail_windows() -> None:
    """
    Expects
    -------
    * Should fail to import if the memory limit is too low

    Note
    ----
    For sklearn on windows, this triggers an OSError with code 22 and winerr 1455
    and so we have to be aware of it before hand.
    There's no automatic way to identfiy this from a regular OSError so we better
    be explicit about it.
    """
    m = Monitor()
    print("Before job ", m.memory("mb"))
    try:
        with limit(
            import_sklearn,
            memory=(100, "mb"),
            wrap_errors={"memory": [(OSError, 22, 1455)]},
        ) as lf:
            lf()
    except MemoryLimitException:
        pass
    except Exception as e:
        print(e, type(e))
        raise e


@pytest.mark.skipif(not plat.startswith("darwin"), reason="darwin specific")
def test_import_fail_mac() -> None:
    """
    Expects
    -------
    * Should fail to import if the memory limit is too low
    """
    with pytest.raises(MemoryLimitException):
        with limit(import_sklearn, memory=(100, "mb")) as lf:
            lf()


def test_import_fail_all() -> None:
    """
    Expects
    -------
    * Should fail to import but give a PynisherException as we can't properly
      identify that it's root cause is due to memory
    """
    m = Monitor()
    print("Before job ", m.memory("mb"))
    try:
        with limit(import_sklearn, wrap_errors=True, memory=(100, "mb")) as lf:
            lf()
    except MemoryLimitException as e:
        raise e
    except PynisherException:
        pass
    except Exception as e:
        print(e, type(e))
        raise e


def test_import_with_enough_memory() -> None:
    """
    Expects
    -------
    * Should import without a problem given enough memory
    """
    with limit(import_sklearn, memory=(1, "GB")) as lf:
        assert lf() is True


if __name__ == "__main__":
    """
    Use this to estimate memory limits. Output on my machine:

    * Before import =  17.83984375
    * After Import sklearn =  671.28515625

    """
    m = Monitor()
    print("Before import = ", m.memory("mb"))

    import sklearn  # noqa

    print("After Import sklearn = ", m.memory("mb"))
