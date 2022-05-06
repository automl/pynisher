from pynisher import (
    CpuTimeoutException,
    MemoryLimitException,
    WallTimeoutException,
    contexts,
    limit,
    supports,
)

import pytest


def import_large_module() -> bytes:
    """Imports a module of size 200MB"""
    import test.test_module_imports.large_module as m

    return m.x


def import_slow_cputime_module() -> bool:
    """Imports a module that keeps cpu busy for 10 seconds"""
    import test.test_module_imports.slow_cputime_module  # noqa

    return True


def import_slow_walltime_module() -> bool:
    """Imports a module that takes 10 walltime seconds"""
    import test.test_module_imports.slow_walltime_module  # noqa

    return True


@pytest.mark.skipif(not supports("memory"), reason="System doesn't support memory")
@pytest.mark.parametrize("context", contexts)
def test_import_large_module(context: str) -> None:
    """
    Expects
    -------
    * A MemoryLimitException should be raised import a module that's too big

    Note
    ----
    The module just consists of a bytearray of 200mb
    """
    with pytest.raises(MemoryLimitException):
        with limit(import_large_module, memory=(100, "MB")) as lf:
            lf()


@pytest.mark.parametrize("context", contexts)
def test_import_slow_cputime_module(context: str) -> None:
    """
    Expects
    -------
    * A CpuTimeoutException should be raised importing a module that takes
      too long to import by cputime measure

    Note
    ----
    The module keeps cpu busy for 10seconds
    """
    with pytest.raises(CpuTimeoutException):
        with limit(import_slow_cputime_module, cpu_time=(1, "s")) as lf:
            lf()


@pytest.mark.parametrize("context", contexts)
def test_import_slow_walltime_module(context: str) -> None:
    """
    Expects
    -------
    * A WallTimeoutException should be raised importing a module that takes
      too long to import by walltime measure

    Note
    ----
    The module sleeps for 10seconds
    """
    with pytest.raises(WallTimeoutException):
        with limit(import_slow_walltime_module, wall_time=(1, "s")) as lf:
            lf()
