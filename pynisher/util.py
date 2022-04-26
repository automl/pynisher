from __future__ import annotations

from typing import Any, Callable

import psutil
from psutil import Process

_mem_unit_table = {
    "B": 1,
    "KB": 2**10,
    "MB": 2**20,
    "GB": 2**30,
}

_time_unit_table = {"s": 1, "m": 60, "h": 60 * 60}


def memconvert(x: float, *, frm: str = "B", to: str = "B") -> float:
    """Convert between memory units

    Parameters
    ----------
    x : float
        The memory amount

    frm : "B" | "KB" | "MB" | "GB" = "B"
        What unit it is in

    to :  "B" | "KB" | "MB" | "GB" = "B"
        What unit to convert to

    Returns
    -------
    float
        The memory amount
    """
    u_from = _mem_unit_table[frm.upper()]
    u_to = _mem_unit_table[to.upper()]

    as_bytes = x * u_from
    as_target = as_bytes / u_to

    # We can't see a use case for float Bytes
    if to.upper() == "B":
        return int(as_target)
    else:
        return as_target


def timeconvert(x: float, *, frm: str = "s", to: str = "s") -> float:
    """Convert between time units

    Parameters
    ----------
    x: float
        The time amount

    frm: "s" | "m" | "h" = "s"
        What unit it is in

    to: "s" | "m" | "h" = "s"
        What unit to convert to

    Returns
    -------
    float
        The time amount
    """
    u_from = _time_unit_table[frm.lower()]
    u_to = _time_unit_table[to.lower()]

    as_seconds = x * u_from
    as_target = as_seconds / u_to

    return as_target


def callstring(f: Callable, *args: Any, **kwargs: Any) -> str:
    """Get a string of the function being called with the args and kwargs

    Parameters
    ----------
    f: Callable
        The function

    *args, **kwargs

    Returns
    -------
    str
        The function call as a str
    """
    parts = list(map(str, args)) + [f"{k}={v}" for k, v in kwargs.items()]
    param_str = ", ".join(parts)
    return f"{f.__name__}({param_str})"


class Monitor:
    def __init__(self, pid: int | None = None):
        """
        Parameters
        ----------
        pid : int | None = None
            The process id to monitor, defaults to current process
        """
        self.process = Process(pid)

    def memory(self, units: str = "B", *, kind: str = "vms") -> float:
        """Get the memory consumption

        Parameters
        ----------
        units : "B" | "KB" | "MB" | "GB" = "B"
            Units to measure in

        kind : "vms" | "rss" = "vms"
            The kind of memory to measure.
            https://psutil.readthedocs.io/en/latest/#psutil.Process.memory_info

        Returns
        -------
        float
            The memory used
        """
        mem = self.process.memory_info()
        if not hasattr(mem, kind):
            raise ValueError(f"No memory kind {kind}, use one from {mem}")

        usage = getattr(mem, kind)
        return memconvert(usage, frm="B", to=units)

    def memlimit(self, units: str = "B") -> tuple[float, float] | None:
        """

        We can't limit using resource.setrlimit as it seems that None of the
        RLIMIT_X's are available. This we debugged by using
        `import psutil; print(dir(psutil))` in which a MAC system did not have
        any `RLIMIT_X` attributes while a Linux system did.

        Parameters
        ----------
        units : "B" | "KB" | "MB" | "GB" = "B"
            Units to measure in

        Returns
        -------
        float | None
            The memory limit.
            Returns None if it can't be gotten
        """
        if hasattr(psutil, "RLIMIT_AS"):
            limits = self.process.rlimit(psutil.RLIMIT_AS)
            if units != "B":
                limits = tuple(memconvert(x, frm="B", to=units) for x in limits)
            return limits
        else:
            return None
